# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import requests
from PIL import UnidentifiedImageError
from PIL import Image
from imquality import brisque
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

from newsutils.crawl import BasePostPipeline
from newsutils.conf import VERSION, SHORT_LINK, PUBLISH_TIME, IMAGES


class SaveToDb(BasePostPipeline):
    """
    Pipeline that saves Post items to the configured database collection,
    the same is named after the date the post.

    #TODO: should replace existing instead of `insert_one()`?
        although `CheckEdits` already takes care of NOT hitting the db
        if existing post is detected, wt of replacing existing posts intentionally?
    """

    def process_post(self):
        """
        Save the post currently being processed by the item pipeline, ie. `self.post
        into the configured MongoDB. Performs an update (vs. an insertion) if the post
        already exists, ie. possesses a database id.
        :return: Post: altered (database operation result), or passed on post.
        """

        post = self.day.save(self.post)
        return post or self.post


class FilterDate(BasePostPipeline):
    """
    Drops posts that :
    - were not published during the specified period
    -  with `publish_time` of None.
    (cf. PostSpider's days_from/to)
    """

    def process_post(self):

        if self.post_time.date() not in self.spider.filter_dates:
            self.log_ok(
                "Dropping expired post: "
                "published time %(publish_time)s outside bounds [%(filter_dates)s]"
                " %(short_link)s" % {
                    'publish_time': self.post[PUBLISH_TIME],
                    'filter_dates': ', '.join([str(d) for d in self.spider.filter_dates]),
                    'short_link': self.post[SHORT_LINK]
                })
            raise DropItem("expired post")
        else:
            assert any([self.post[PUBLISH_TIME] != d
                        for d in ['2022-04-09', '2022-04-10']]),\
                'found 2022-04-09'
            return self.post


class CheckEdits(BasePostPipeline):
    """
    Creates new version of posts whose content has changed
    Updates posts with only minor changes
    Drops otherwise all duplicate posts.

    Pipeline must have relatively high priority in `settings.ITEM_PIPELINES`.
    """

    _ids_seen = {}

    @property
    def ids_seen(self) -> set[str]:
        # FIXME: not resilent if `item.get(self.item_id_field)` returns None,
        #  ie, if db yields row with no `item_id_field`. FIX: filter(lambda x: x, l)
        if self.day.date not in self._ids_seen:
            self._ids_seen[self.day.date] = \
                set(map(lambda it: it.get(self.item_id_field), self.day.find(
                    projection={self.item_id_field: True, '_id': False})))
        return self._ids_seen[self.day.date]

    def process_post(self):

        adapter = ItemAdapter(self.post)
        item_id_field = adapter[self.item_id_field]  # or self.post[self.item_id_field] ???
        version_field = VERSION

        # new posts (unseen) are sent down the pipeline right away, whereas
        # edited versions of existing posts are further processed based on
        # the nature of the edit. non-modified (pristine) posts are dropped.
        if item_id_field not in self.ids_seen:
            self.ids_seen.add(item_id_field)
        else:
            existing_post, status = self.check_edits()

            if status['pristine']:
                # identical post matched in database
                # drop duplicate post (prevents from reaching the `SaveToDb` pipeline)
                self.log_ok(f"dropping duplicate post: {item_id_field}")
                raise DropItem("duplicate post")

            if status['new_version']:
                # content was altered in a major way, suggests new version of post
                # increment post version, also return post without id for new post
                # creation by the `SaveToDb` pipeline
                adapter[version_field] = int(existing_post[version_field]) + 1
            else:
                # otherwise, consider the update minor, and update existing post
                # returning post with `_id` attribute set will trigger an update
                # by the `SaveToDb` pipeline instead of an insert
                adapter.update({'_id': existing_post['_id']})  # sets `_id` from existing db post

        # will probably get saved to db.
        return adapter.item

    def check_edits(self, updated_fields=None):
        """
        Detect post changes.
        Enforcing action to take against changes is left to caller.

        :param updated_fields: changes in `fields` will trigger a new version of the
            current post to be created. defaults to content fields alone.
        :return: (existing_post, status)
            status: **pristine**, post is identical to existing one
                    **new_version**, post is new version of existing post
        """
        # default policy: `pristine`
        # should cause caller to drop already existing posts
        status = dict(pristine=True, new_version=False)

        all_fields = list(self.post.fields)
        excluded_fields = self.edits_excluded_fields
        new_version_fields = self.edits_new_version_fields
        existing_post = self.day.find_one({self.item_id_field: self.post[self.item_id_field]})

        have_changed = lambda fields: any(
            [self.post[f] != existing_post[f] for f in fields
             if f not in excluded_fields])

        if existing_post:
            status['pristine'] = not have_changed(all_fields)
            status['new_version'] = have_changed(new_version_fields)

        return existing_post, status


class DropLowQualityImages(BasePostPipeline):
    """
    Discards poor quality images from posts before they get saved to the db.
    ie., too small sized, too poor (high BRISQUE score) quality.
    Does not carry out any database operation.
    Does not drop posts, only alters their 'images' property.

    Nota:
        - Keep above `SaveToDb` in `settings.ITEM_PIPELINES`
        - Uses more time and processing power.

    #FIXME: Replace PIL with `skimage`, which already is a dependency of `imquality.brisque`
    #TODO: BRISQUE doesn't check PSNR (Peak SNR). Check PSNR as well?
        PSNR not very reliable, Cf. https://www.youtube.com/watch?v=Vj-YcXswTek.
    #TODO: further img quality checks of dpi, height/width (using im.info, im.size, im.encoderinfo)
        i) run some kind of statistical test @5% based on the median.
        ii) what distrib of the images to assume then? non-parametric? or,
             assume a normal of images in website (cumulate samples in the database)?

    """

    log_prefix = "drop noqa images"

    def process_post(self):
        self.validate_images()
        return self.post

    def validate_images(self):
        """
        Image field validation.
        Edits the post's `images` property in place.
        """

        def has_acceptable_size(image: Image):
            min_w, min_h = self.image_min_size
            return image.width >= min_w and \
                   image.height >= min_h

        def has_acceptable_quality(image: Image):
            """
            Uses BRISQUE (Blind Reference-less Image Spatial Quality Evaluator)
            Refs:
                https://live.ece.utexas.edu/publications/2012/TIP%20BRISQUE.pdf
                https://towardsdatascience.com/automatic-image-quality-assessment-in-python-391a6be52c11
                https://learnopencv.com/image-quality-assessment-brisque/

            Errors Refs:
                https://giters.com/ocampor/image-quality/issues/23?amp=1
            """
            try:
                return brisque.score(image) <= \
                       self.image_brisque_max_score
            except Exception as exc:
                self.log_failed(image.shortname_, exc)
                return self.image_brisque_ignore_exception

        keep_images = []
        for url in self.post[IMAGES]:
            try:
                im = Image.open(requests.get(url, stream=True).raw)
                im.filename = im.filename or url
                im.shortname_ = im.filename.rsplit("/", 1)[-1]  # pseudo prop
            except UnidentifiedImageError:
                continue

            if has_acceptable_size(im) and has_acceptable_quality(im):
                keep_images.append(url)
                self.log_ok(im.shortname_)

        # log stats
        self.stats["total"] = len(self.post[IMAGES])
        self.stats["ok"] = len(keep_images)
        self.log_ended("(stats): succeeded {ok}/{total} images", **self.stats)

        # patch post, keep valid images only
        self.post[IMAGES] = keep_images

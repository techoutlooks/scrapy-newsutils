import datetime
import hashlib
from typing import Iterable
from urllib.parse import urlparse

from daily_query.helpers import mk_datetime
from newsnlp import TextSummarizer, TitleSummarizer, Categorizer, TfidfVectorizer
from newsnlp.ad import extract_domain, AD_LABEL_COLUMN
from newsnlp.ad.models.ad_detector import predict_ads

from newsutils.conf import LINK, TaskTypes, SHORT_LINK, LINK_HASH
from newsutils.conf.mixins import PostConfigMixin
from newsutils.crawl import Day
from newsutils.helpers import wordcount, uniquedicts, dictdiff, add_fullstop, compose
from newsutils.crawl.items import BOT, THIS_PAPER
from newsutils.conf.post_item import Post, mk_post
from newsutils.conf import \
    TITLE, METAPOST, SCORE, COUNTRY, TYPE, AUTHORS, PUBLISH_TIME, VERSION, \
    MODIFIED_TIME, IMAGES, VIDEOS, TAGS, IS_DRAFT, IS_SCRAP, KEYWORDS, TOP_IMAGE, PAPER, UNKNOWN
from newsutils.spiderloader import load_spider_contexts


__all__ = (
    "CATEGORY_NOT_FOUND",
    "predict_post_image_ads",
    "DayNlp"
)


CATEGORY_NOT_FOUND = 'N/A'


def predict_post_image_ads(post_url: str):
    """
    Performs ad detection per each post image, that analyses several dimensions like:
    the geometrical images properties (width, height, size), image src, click destination,
    as well the surrounding context of images (caption, alt).
    """
    from newsnlp.ad.dataset import extract_ad_candidates_from_url

    # load spider context for url
    domain = extract_domain(post_url)
    spider_ctx = next(load_spider_contexts(domain=domain))
    if not spider_ctx:
        return []

    # pipeline items to derive images xpaths from spider context,
    # and extract ad candidate from resulting xpaths
    clean_xpath = lambda x: x.strip('@src') if x.endswith('@src') else x
    get_link_xpath = lambda x: f"{x}parent::a"
    extract_ad_candidates_from_xpath = lambda x: extract_ad_candidates_from_url(post_url, x, raise_exc=False)
    img_xpaths = set([v for rule in spider_ctx['rule_sets'].items()
                for (k, v) in rule[1].items() if k == 'images'])

    # execute pipeline to get data suitable for feeding the ad prediction model
    # perform ad prediction inference
    fetch_ad_candidates = compose(extract_ad_candidates_from_xpath, get_link_xpath, clean_xpath)
    ad_candidates = sum([list(fetch_ad_candidates(x)) for x in img_xpaths], [])
    return predict_ads(ad_candidates)


def clean_post_images(post: Post):

    ad_imgs_urls = map(lambda p: p['_raw']['img_url'],
        filter(lambda p: p[AD_LABEL_COLUMN], predict_post_image_ads(post[LINK]))
    )

    # comparing relative paths since `extract_ad_candidates_from_url()`
    # might have returned relative img paths
    post[IMAGES] = [u for u in post[IMAGES] if urlparse(u).path not in ad_imgs_urls]


class DayNlp(Day, PostConfigMixin):
    """
    Helper to perform NLP on posts scraped a given day .
    Performs following tasks, operating as a whole, on the posts generated any given day:
    - Compute and update similarity scores of all posts with given date, to the db
    - Generate and save metaposts from sibling posts; cf. below note (1).

    Notes:
    ------
        (1) Similar posts of a given post are split in two categories:
          - sibling posts, with a similarity score >= `settings['POSTS'].similarity_siblings_threshold`
          - related posts, with a similarity score >= `settings['POSTS'].similarity_related_threshold`,
            but inferior to `.similarity_siblings_threshold`.
        (3) Meta posts are posts with type `metapost.*` (* in ['default', 'featured'] summarised from
            the siblings of any given post into their 'caption', 'summary', and 'category' attributes.

    FIXME: bugs if generating metaposts before computing similarity.
    """

    # TODO: multi-language
    lang = "fr"

    def __init__(self, *args, **kwargs):

        # set task_type -> NLP so we don't load nor add metaposts to loaded posts (ie. `self.posts`)
        # cf. `Day.save()`
        super().__init__(*args, task_type=TaskTypes.NLP, **kwargs)

        # processing start, both for timing execution, and as a checkpoint
        # to recognize new data (eg. posts edited/inserted by this process)
        self.start_time = datetime.datetime.now(datetime.timezone.utc)

        self.counts = dict(
            # resp. total posts processed/saved, words processed
            total=0, saved=0, words=0,
            # tfidf, (text, title, category)-summarization, meta-summarization
            similarity=0, summary=0, metapost=0
        )

        # nlp models
        corpus = filter(None, [self.get_decision("get_post_text")(p) for p in self.posts])
        self.vectorizer = TfidfVectorizer(lang="fr")(corpus)
        self.categorizer = Categorizer(lang="fr")
        self.text_summarizer = TextSummarizer(lang=self.lang)
        self.title_summarizer = TitleSummarizer(lang=self.lang)

        # stats for the day
        self.counts['similarity'] = self.vectorizer.num_docs
        self.counts['words'] = self.vectorizer.corpus_len
        self.counts['total'] = len(self.posts)

    def save_day(self, verb=None):

        def build_params(verb):
            params = {
                "similarity": {},
                "summary": {},
                METAPOST: {},
            }

            # no verb, runs them all !
            return {verb: params.get(verb)} if verb \
                else params

        for verb, params in build_params(verb).items():
            for post in self.posts:
                save = getattr(self, "save_%s" % verb)
                _, status = save(post, **params)
                self.counts["saved"] += status

        self.log_ended(
            "saved ({saved}) fields in ({total}) docs, ({words}) words: "
            "generated (similarity/summary/metapost): {similarity}/{summary}/{metapost} posts. "
            f"published on {self}.", **self.counts)

        return self.counts

    def save_similarity(self, post: Post, overlap=False):
        """
        Compute similarity (`siblings`, `related` by default) scores
        of given post against the entire corpus., and persist it to the db.
        Docs are partitioned by similarity using respective threshold level.

        :param Post post: post doc to save similarity for
        :param bool overlap: include results from higher thresholds into lower ones?
        :returns: saved (post, count).
        :rtype: (Post, int)

        TODO: use only half the symmetric TF-IDF matrix to speed up the task
        TODO: use optimised TF-IDF function from Spacy or Sklearn, instead of hand-crafted one
        """

        # uses tfidf model to vectorise title+text of entire article corpus
        # `.similarity` holds params for the model's `similar_to` api.
        similar, saved = {}, 0
        log_msg = \
            f"{'' if saved else 'NOT'} saving `{list(self.similarity)}` similarity " \
            f"({saved}) siblings, for doc #{post[self.db_id_field]} ..."

        for field, tfidf_params in self.similarity.items():

            # compute similar_docs and transform as db format, like so:
            # [{'_id': ObjectId('6283bcb2c176579f86acafb0'), 'score': 0.14859620818206487}, ...]
            similar_docs = self.get_similar(post, **tfidf_params)
            db_value = [{self.db_id_field: p[self.db_id_field], SCORE: score}
                        for p, score in similar_docs]

            # remove previous intersecting doc sets. generated sets have
            # cardinals inversely proportional to resp. similarity scores
            if not overlap:
                db_value = dictdiff(db_value, *similar.values())

            similar[field] = db_value

        try:
            if similar:
                post = self.save(Post({**post, **similar}))
            self.log_ok(log_msg)

        except Exception as exc:
            self.log_failed(log_msg, exc, saved)

        saved = int(bool(post))
        self.counts["similarity"] += saved
        return post, saved

    def save_summary(self, post: Post, **kwargs):
        """
        Generate (destructive) abstractive summaries (title, text, categories)
        for given post, using computed values, and persist it to the database.

        :returns: saved (post, count).
        :rtype: (Post, int)
         """

        # don't attempt summarising if min text length requirement not met
        text = self.get_decision("get_post_text")(post)
        if not text:
            return post, 0

        summary, caption, categories = self.get_summary(text)
        category = categories[0][0] if categories else CATEGORY_NOT_FOUND

        log_msg = \
            f"generating `summary` for doc #`{post[self.db_id_field]}`: " \
            f"summary: ({wordcount(summary)}/{wordcount(text)}) words, " \
            f"caption: ({wordcount(caption)}/{wordcount(post[TITLE])}) words, " \
            f"category: `{category}`."

        try:
            post = self.save(Post({
                **post,
                self.caption_field: caption,
                self.summary_field: summary,
                self.category_field: category}))
            self.log_ok(log_msg)

        except Exception as exc:
            self.log_failed(log_msg, exc)

        saved = int(bool(post))
        self.counts["summary"] += saved
        return post, saved

    def save_metapost(self, src: Post, **kwargs):
        """ Generate a meta post from given post's siblings,
         and save it to the database in the same collection. """

        metapost, saved = None, 0
        log_msg = \
            f"generating `{METAPOST}` " \
            f"{'#' + str(metapost[self.db_id_field]) if metapost else ''} " \
            f"for post #{src[self.db_id_field]}: "

        metapost, lookup_version = self.mk_metapost(src, **kwargs)
        if metapost:
            try:
                # checks if exists a previous version of metapost in the db.
                # only alters posts with same type, ie. `metapost.*`
                metapost = self.save(metapost, only=(TYPE,),
                                     id_field_or_match={'version': lookup_version})
                self.log_ok(log_msg)
            except Exception as exc:
                self.log_failed(log_msg, exc)

        saved = int(bool(metapost))
        self.counts[METAPOST] += saved
        return metapost, saved

    def mk_metapost(self, src: Post, **kwargs):
        """ Generate a meta post by compiling all siblings
        of the given post, given the configured strategy.

        Nota:
        -----
        (1) mk_metapost do NOT set following fields: TITLE, TEXT, EXCERPT.
            Instead, summarization assigns a new set of fields: 'caption', 'title', 'category'.
        (2) No `_id` field is generated from metaposts. This is left to the database engine.
        (3) LINK, SHORT_LINK, LINK_HASH fields init is deferred to the
            `Day.save(transform=...)` method,
            since links include the `db_id_field` of posts, only available after hitting the db.

        CAUTION: relies on `.save_summary()` to set values for fields `siblings`, `related`

        TODO: summarizer currently only supports 1024 words max.
            find more powerful model? push model capacity?
            trim each text according to num_texts/1024 ratio.

        :returns: saved (metapost, count).
        :rtype: Post
        """
        metapost, lookup_version = None, None

        # TODO: leverage fact that similarity is a symmetric function to improve speed by x2.
        # TODO: strategy to get metapost from other methods than TF-IDF, eg. kNN, kernels?
        siblings = self.get_similar(src, from_field=self.siblings_field)
        siblings, _ = zip(*siblings) if siblings else ([], [])
        siblings_texts = [self.get_decision("get_post_text")(p, meta=True) for p in siblings]
        _text = " ".join([add_fullstop(t) for t in filter(None, siblings_texts)])

        # skip if no _text, ie., no siblings found to infer metaposts
        if not _text:
            return metapost, lookup_version

        metapost = mk_post()

        # `lookup_version`: possible existing database version of this metapost
        # It corresponds to previous siblings of this post, ie. that were not added by the current process.
        old_siblings = filter(lambda p: p[self.db_id_field].generation_time <= self.start_time, siblings)
        lookup_version = self.mk_metapost_version(old_siblings)

        # the current version
        # ie. after `.save_similarity()` may have added more siblings to `src` post.
        metapost[VERSION] = self.mk_metapost_version(siblings)

        # NLP fields. Models inference happen here.
        summary, caption, categories = self.get_summary(_text)
        category = categories[0][0] if categories else CATEGORY_NOT_FOUND
        metapost[self.category_field] = category
        metapost[self.caption_field] = caption
        metapost[self.summary_field] = summary

        # siblings & related
        # from src post
        metapost[self.siblings_field] = src[self.siblings_field]
        metapost[self.related_field] = src[self.related_field]

        # immutable fields
        # `TOP_IMAGE` from most similar post (highest score)
        # `MODIFIED_TIME` is now
        metapost[TYPE] = "%s.%s" % (METAPOST, src[TYPE])
        metapost[COUNTRY] = src[COUNTRY]
        metapost[PUBLISH_TIME] = str(mk_datetime(self))
        metapost[MODIFIED_TIME] = str(mk_datetime())
        metapost[TOP_IMAGE] = siblings[0][TOP_IMAGE]
        metapost[PAPER] = THIS_PAPER
        metapost[AUTHORS] = [BOT]

        # compile misc. data from siblings into metapost:
        # bool fields, str list fields, dict list fields
        for post in siblings:

            for f in IS_DRAFT, IS_SCRAP:  # bools
                metapost[f] &= post[f]
            for f in IMAGES, VIDEOS, KEYWORDS, TAGS:  # strs
                metapost[f] = list(set(metapost[f]).union(post[f]))
            for f in AUTHORS, :  # dicts
                metapost[f] = uniquedicts(metapost[f], post[f])

        # patch images: filter out unwanted images
        # analyses context of images in src post
        # FIXME: extensive testing
        # metapost[IMAGES] = list(clean_post_images(src))

        return metapost, lookup_version

    def mk_metapost_version(self, posts: Iterable[Post]) -> str:
        """ Predictable version hash for metapost.
        Generated from siblings posts' ObjectId's. """
        _posts = sorted(posts, key=lambda p: p[self.db_id_field].generation_time)
        return hashlib.md5(
            ''.join([str(p[self.db_id_field]) for p in _posts]).encode()
        ).hexdigest()

    def get_summary(self, text: str):

        summary = self.text_summarizer(text)
        caption = self.title_summarizer(text)
        categories = self.categorizer(text)
        return summary, caption, categories

    def get_similar(self, post, from_field=None, **kwargs):
        """
        Get (<post>, <similarity-score>) of posts similar to `post`,
        having similarity score of equal or above value `kwargs['threshold']`

        :param str from_field: re-run TF-IDF (the default)? or return post defaults.
        :param Post post: post whose similar docs are sought
        :param kwargs: optional params for `TfidfVectorizer`, (ie. `threshold`, `top_n`)
        :returns: [(Post, int)] : [( <post>, <score>), ...] of similar docs
        """

        if from_field:
            similar = self.expand_related(post, from_field)
            similar = list(map(lambda args: (args[0], args[1].get(SCORE)), similar))

        else:
            post_i: int = self.posts.index(post)
            similar = self.vectorizer.similar_to(post_i, **kwargs)
            similar = [(self.posts[j], score) for j, score in similar]

        log_msg = lambda post_score: \
            f"found ({len(similar)}) docs similar to " \
            f"#{post[self.db_id_field]} (@{post_score}) : " \
            f"{', '.join(['#{} (@{:.2f})'.format(p[self.db_id_field], score) for p, score in list(similar)])}"

        # threshold can't be recovered from db-saved post!
        score = UNKNOWN if from_field else kwargs.get('threshold')
        self.log_ok(log_msg, score)

        return similar

    def expand_related(self, post: Post, field: str):
        """
        Expand the posts referred to by the `field` attribute of given post
        into plain Post objects

        :returns [(Post, dict)]: list of resp. the referred-to post and
                existing db value (value for `field`)
        """
        related: [Post] = []
        db_related = post.get(field)
        if db_related:
            for db_post in db_related:
                item_id = db_post.get(self.db_id_field)
                if item_id:                         # get the next post that matches
                    post = next(filter(              # id of the related item
                        lambda p: p[self.db_id_field] == item_id, self.posts), None)
                    if post:
                        related += [(post, db_post)]    # return existing value for field as well

        return related


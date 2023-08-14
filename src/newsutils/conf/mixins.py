import abc
from collections import OrderedDict

from scrapy.utils.project import get_project_settings

from .globals import get_setting
from .constants import TaskTypes, EXCERPT, TITLE, TEXT
from ..helpers import add_fullstop, import_attr, evalfn, classproperty, compose
from ..logging import TaskLoggerMixin
from ..storage import upload_blob_from_url


__all__ = (
    "BaseConfigMixin", "PostStrategyMixin", "PostConfigMixin",
    "SportsConfigMixin",
    "StorageUploadMixin",
    "metapost_link_factory"
)


# metapost link creator function.
# this is patched dynamically with the callable referenced by the
# `POSTS.metapost_link_creator` project setting (`src/newsutils/conf/posts.py`).
metapost_link_factory = lambda baseurl, db_id_field: "%s/%s" % (
    baseurl.strip("/"), db_id_field)


@evalfn  # auto-setup factory on init.
def _set_metapost_link_factory():
    """
    Dynamically load the metapost link factory function, used to generate the metapost's `link` and
    `short_link` attributes.
    from the `POSTS.metapost_link_creator` Scrapy setting. The setting's value must be
    a dotted path (string) referencing the create link function.

    If no user-defined factory set, loads the default factory (`newsutils.conf.mixins.metapost_link_factory`)
    which merely concatenates `POSTS.metapost_baseurl` with the metapost's `id_field`.
    """
    global metapost_link_factory
    value = get_setting('POSTS.metapost_link_factory')
    metapost_link_factory = import_attr(value)


class BaseConfigMixin(TaskLoggerMixin):
    """
    Mixin. Exposes utility class attributes.
    The project's settings module will get automagically patched by the `newsutils` library,
    on import, with useful defaults; or by calling `newsutils.configure_posts()` explicitly.
    """

    @classproperty
    def settings(self):
        return get_project_settings()

    @classproperty
    def default_settings(self):
        # `default_settings = settings` required to prevent override of `.settings`
        # by the `cmdline.py` module when calling `.process_options()`
        return self.settings

    db_uri = get_setting("DB_URI")
    db_id_field = get_setting("DB_ID_FIELD")
    media_storage = get_setting("MEDIA_STORAGE")
    is_dev = get_setting("ENV") == "development"


# closure, so the proper value for key is found in the enclosing scope of make_fget
# when fget gets called, https://stackoverflow.com/a/27630089
def make_fget(key):
    def fget(self):
        return get_setting(f"POSTS.{key}")
    return fget


class PostConfigMeta(abc.ABCMeta):
    """
    Metaclass for generating post config utility subclasses
    with field values extrapolated dynamically.

    Nota: `item_id_field`: Identifies crawled items uniquely. NOT the database id.
    """

    def __new__(mcs, class_name, bases, attrs):

        field_groups = {
            'item': ['item_id_field', 'computed_fields', 'crap_banned_keywords', 'crap_similarity_threshold'],
            'image': ['image_min_size', 'image_brisque_max_score', 'image_brisque_ignore_exception'],
            'versioning': ['edits_excluded_fields', 'edits_new_version_fields', 'edits_pristine_threshold',
                           'edits_new_version_threshold'],
            'nlp': ['caption_field', 'category_field', 'summary_field', 'siblings_field', 'related_field',
                    'summary_minimum_length', 'nlp_uses_excerpt', 'meta_uses_nlp'],
        }

        new_attrs = {f: classproperty(make_fget(f))
                     for f in sum(field_groups.values(), [])}

        new_attrs.update(attrs)
        return super().__new__(mcs, class_name, bases, new_attrs)


class PostConfigMixin(BaseConfigMixin, metaclass=PostConfigMeta):
    """
    Mixin. Exposes utility class attributes.
    """

    @classproperty
    def metapost_fields(self):
        return [self.category_field, self.caption_field, self.summary_field]

    @property
    def similarity(self):
        """ Settings for computing similarity scores amongst posts
        keys are also the proper kwargs of `TfidfVectorizer.similar_to()`
        """
        config = {
            self.siblings_field: {
                "threshold": self.settings['POSTS']['similarity_siblings_threshold'],
                "top_n": self.settings['POSTS']['similarity_max_docs']
            },
            self.related_field: {
                "threshold": self.settings['POSTS']['similarity_related_threshold'],
                "top_n": self.settings['POSTS']['similarity_max_docs']
            },
        }

        config = OrderedDict(dict(sorted(
            config.items(), key=lambda it: it[1]["threshold"], reverse=True)))
        return config


class PostStrategyMixin(PostConfigMixin):
    """
    Post handling strategy.
    """

    @classmethod
    def get_decision(cls, rule: str):
        """
        Yields functions for per-post decisions, based on the
        post's current value and configured settings
        """

        def filter_metapost(post, task_type=None):
            """
            Whether to filter out the current post if it is a metapost?
            Post is dropped (returns None) on any of the following conditions:
                - project is set to exclude metaposts from NLP tasks inputs.
                -
            cf. `newsutils.conf.settings`

            :param Post|None post: the post to make the decision about
            :param TaskTypes task_type: identifies the kind of task that is processing the post
            """
            if not post:
                return

            if post.is_meta \
                    and task_type == TaskTypes.NLP \
                    and not cls.settings['POSTS']['nlp_uses_meta']:
                return  # filtered out
            return post

        def get_post_text(post, meta=False, minimum_length=0) -> str or None:
            """
            Get all meaningful text from post, post's title and body alike.

            :param bool meta: a metapost being generated,
                    but `post` is unaware (post.is_meta not set yet)
            :param Post post: the post item
            :param int minimum_length: minimum text length required
            """
            if not post:
                return

            # iff regular post
            uses_nlp = not post.is_meta and cls.settings['POSTS']['nlp_uses_excerpt']
            title, text = (TITLE, EXCERPT if uses_nlp else TEXT)

            # iff metapost
            if post.is_meta or meta:
                uses_nlp = cls.settings['POSTS']['meta_uses_nlp']
                title, text = (cls.caption_field if cls.meta_uses_nlp else TITLE,
                               cls.summary_field if cls.meta_uses_nlp else TEXT)

            post_text = add_fullstop(post[title]) + " " + (post[text] or "")
            if len(post_text) < int(minimum_length or cls.summary_minimum_length):
                post_text = None

            return post_text

        def get_metapost_link(metapost):
            baseurl = cls.settings['POSTS']['metapost_baseurl']
            return metapost_link_factory(baseurl, str(metapost[cls.db_id_field]))

        return {
            "filter_metapost": filter_metapost,
            "get_post_text": get_post_text,
            "get_metapost_link": get_metapost_link
        }.get(rule)


class SportsConfigMixin(BaseConfigMixin):
    pass


upload_from_urls = lambda urls: filter(None, map(lambda u: upload_blob_from_url(
    u, PostConfigMixin.media_storage, raise_exc=False), urls))


class StorageUploadMixin(PostConfigMixin):
    """
    Facility to upload files to a Google Cloud Storage bucket.
    """

    @classmethod
    def from_urls(cls, image_urls: [str]) -> [str]:
        get_uploads = compose(lambda blobs: map(
            lambda b: b.public_url, blobs), upload_from_urls)
        return get_uploads(image_urls)

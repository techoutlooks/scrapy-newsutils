from collections import OrderedDict

from scrapy.utils.project import get_project_settings

from . import get_setting
from .constants import TaskTypes, EXCERPT, TITLE, TEXT
from ..helpers import add_fullstop, get_env, import_attr, evalfn
from ..logging import TaskLoggerMixin


__all__ = (
    "BaseConfigMixin", "PostStrategyMixin", "PostConfigMixin",
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
    """

    # the project's settings module will get automagically patched
    # by the `newsutils`library, on import, with useful defaults.
    # `default_settings = settings` required to prevent override of `.settings`
    # by the `cmdline.py` module when calling `.process_options()`
    settings = get_project_settings()  # FIXME: needed? delete since os.sys['settings'] already patched!
    default_settings = settings

    # DATABASE FIELDS
    # `item_id_field`: Identifies crawled items uniquely. NOT the database id.
    db_uri = settings["CRAWL_DB_URI"]
    db_id_field = settings['DB_ID_FIELD']


class PostConfigMixin(BaseConfigMixin):
    """
    Mixin. Exposes utility class attributes.
    """

    # FIXME: fields polluting the namespace,
    #    use DataClassCard in AppSettings? or set attrs here from snake_cased settings?
    settings = BaseConfigMixin.settings

    # ITEM
    # `item_id_field`: Identifies crawled items uniquely. NOT the database id.
    item_id_field = settings['POSTS']['item_id_field']

    # NLP FIELDS
    caption_field = settings['POSTS']['CAPTION_FIELD']
    category_field = settings['POSTS']["CATEGORY_FIELD"]
    summary_field = settings['POSTS']['SUMMARY_FIELD']
    siblings_field = settings['POSTS']["SIBLINGS_FIELD"]
    related_field = settings['POSTS']["RELATED_FIELD"]

    # MISC FIELDS
    computed_fields = settings['POSTS']['COMPUTED_FIELDS']
    edits_excluded_fields = settings['POSTS']["EDITS_EXCLUDED_FIELDS"]
    edits_new_version_fields = settings['POSTS']["edits_new_version_fields"]
    image_min_size = settings['POSTS']['image_min_size']
    image_brisque_max_score = settings['POSTS']['image_brisque_max_score']
    image_brisque_ignore_exception = settings['POSTS']['image_brisque_ignore_exception']

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
            if post.is_meta \
                    and task_type == TaskTypes.NLP \
                    and not cls.settings['POSTS']['nlp_uses_meta']:
                return  # filtered out
            return post

        def get_post_text(post, meta=False):
            """
            Get all meaningful text from post, post's title and body alike.

            :param bool meta: a metapost being generated,
                    but `post` is unaware (post.is_meta not set yet)
            :param Post post: the post item
            """

            # default
            uses_nlp = not post.is_meta and cls.settings['POSTS']['summary_uses_nlp']
            title, text = (TITLE, EXCERPT if uses_nlp else TEXT)

            # metapost only
            if post.is_meta or meta:
                uses_nlp = cls.settings['POSTS']['meta_uses_nlp']
                title, text = (cls.caption_field if uses_nlp else TITLE,
                               cls.summary_field)

            return add_fullstop(post[title]) + " " + (post[text] or "")

        def get_metapost_link(metapost):
            baseurl = cls.settings['POSTS']['metapost_baseurl']
            return metapost_link_factory(baseurl, str(metapost[cls.db_id_field]))

        return {
            "filter_metapost": filter_metapost,
            "get_post_text": get_post_text,
            "get_metapost_link": get_metapost_link
        }.get(rule)


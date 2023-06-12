from collections import OrderedDict

from scrapy.utils.project import get_project_settings

from .constants import TaskTypes, EXCERPT, TITLE, TEXT
from ..helpers import add_fullstop, get_env
from ..logging import TaskLoggerMixin


__all__ = (
    "BaseConfigMixin", "PostStrategyMixin", "PostConfigMixin",
)


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

        return {
            "filter_metapost": filter_metapost,
            "get_post_text": get_post_text,
        }.get(rule)


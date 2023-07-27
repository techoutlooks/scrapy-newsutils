from ..helpers import get_env
from ..appsettings import AppSettings
from newsutils.conf.constants import *

__all__ = ("configure_posts",)

# Dotted path to Project settings module.
# eg. SCRAPY_SETTINGS_MODULE=crawl.settings
settings_module = get_env('SCRAPY_SETTINGS_MODULE')

# defaults for computed field names as
# populated/persisted by the `NlpDaily` util class
_nlp_base_fields_conf = {

    # summarization
    "category_field": "category",
    "caption_field": "caption",
    "summary_field": "summary",

    # similarity
    "siblings_field": "siblings",
    "related_field": "related",
}


def configure_posts():
    """
    Merges app settings with scrapy settings,
    Patches stdlib imports for both the scrapy project settings `crawl.settings`, and
    the default settings `scrapy.settings.default_settings`,

    :return merged settings dict.
    """

    # inject app-defined settings (`Posts`) inside the Scrapy settings,
    # merges (resp. to precedence) env-defined, project-defined and default settings.
    settings = Posts()(settings_module, 'scrapy.settings.default_settings')

    # == [ COMPUTED SETTINGS] ==
    # define `computed` settings, typically computed based on other configurable settings.
    # these are loaded dynamically here to ensure they effectively reflect dynamic changes
    # of their dependent settings; especially env vars updates.
    posts_config = settings.config
    db_id_field = settings["DB_ID_FIELD"]

    posts_config["nlp_base_fields"] = \
        [posts_config[f] for f in list(_nlp_base_fields_conf)]

    posts_config["nlp_fields"] = \
        posts_config["nlp_base_fields"] + \
        [TAGS, KEYWORDS, EXCERPT]

    posts_config["computed_fields"] = \
        [db_id_field] + \
        posts_config["nlp_base_fields"] + [posts_config[f] for f in (
            'item_id_field',
        )]

    posts_config["edits_excluded_fields"] = [
        VERSION,
        db_id_field,
        posts_config["item_id_field"],
        *posts_config["nlp_fields"],
    ]

    return settings.settings


class Posts(AppSettings):
    """
    Default settings for the posts scraper.
    A value of `None` signifies a required setting

    TODO: shift to [Pydantic](https://docs.pydantic.dev/usage/settings/)?
    TODO?: prefix with `DEFAULT_` ??
    FIXME: make `item_id_field`, `nlp_fields` lazily loaded
        since they depend on other dynamics settings.

    """

    # Scrapy settings (overrides)
    # -----------------------------------------------------------------------------
    LOGGING = False
    LOG_FORMATTER = 'scrapy.logformatter.LogFormatter'
    SPIDER_LOADER_CLASS = 'newsutils.spiderloader.DatabaseSpiderLoader'
    ITEM_PIPELINES = {
        'newsutils.pipelines.FilterCrap': 100,
        'newsutils.pipelines.FilterDate': 110,
        'newsutils.pipelines.CheckEdits': 120,
        'newsutils.pipelines.DropNoqaImages': 200,
        'newsutils.pipelines.SaveToDb': 300
    }

    # Custom settings (scrapy-newsutils)
    # -----------------------------------------------------------------------------
    # TODO: replace MongoDB with CouchDB
    # MongoDB only is supported. This is temporary.
    # BasePipeline's `get_setting` raises an exception if settings are not defined.
    CRAWL_DB_URI = 'mongodb://localhost:27017/scraped_news_db'
    CRAWL_DB_SPIDERS = '_spiders'

    # DB_ID_FIELD: row id from the database engine
    DB_ID_FIELD = '_id'

    BRANDING = {
        "bot_image_url": None,
        "logo_url": None
    }

    # use lowercase field names inside `POST` setting
    POSTS = {

        "default_lang": "en",

        # POST
        # =============================================================================================
        # per-post editable/computed fields values.
        #
        # auto_publish: controls the`.is_draft` state of newly created posts
        #       if True (the default), hints that the post is created in its final version once for all.
        # item_id_field: NOT the database id. yields unique posts accurately for handling by the
        #       `.process_post()` pipeline fn. must NOT be set to the `db_id_field`,
        #       eg. CheckEdits pipeline which relies on `item_id_field` to find an existing version
        #       of a post in the database, given that pipeline items have by definition no value for
        #       `db_id_field` (didn't hit the db yet).
        # DB_ID_FIELD: the database id
        "auto_publish": True,
        "item_id_field": SHORT_LINK,
        **_nlp_base_fields_conf,

        # NLP
        # =============================================================================================
        # section defines inputs for decision making by NLP tasks (see `nlp` module).
        # cf. `newsutils.crawl.get_strategies()`, yields decision  based on below inputs
        # **tasks** : `similarity`, `summary`, `metapost` generation.
        #
        # nlp_uses_meta: also add metaposts (type==METAPOST) as inputs to NLP tasks?
        # summary_uses_nlp: (iff !metapost type), use text from `excerpt` field instead of `text` field?
        # meta_uses_nlp: metapost generation: use text from `caption` field instead of `title` field?
        # don't attempt summarising if min text length requirement not met
        "nlp_uses_meta": False,
        "summary_uses_nlp": False,
        "meta_uses_nlp": True,
        "metapost_baseurl": None,  # required
        "metapost_link_factory": 'newsutils.conf.mixins.metapost_link_factory',
        "summary_minimum_length": 100,

        # PIPELINES
        # =============================================================================================
        # Following settings control management of post pipelines
        #
        # banned_keywords:  ban pipeline item altogether iff post has <<similar>> keywords
        #       cf. `newsutils.pipelines.similarity()` defines the similarity (Jaccard measure).
        # image_min_size: images should be at least 200x150 px to save to db

        # image_brisque_ignore_exception: defaults to disregard image quality inspection on error.
        # edits_new_version_fields: fields whose values changes suggest a new post version
        #       subsequently increased by the `CheckEdits` pipeline
        # edits_excluded_fields: computed fields, post version checks should not account for their values,
        #       since they are dynamic.

        # cloudfare yields .36
        "crap_banned_keywords":  ['protecting', 'protection', 'protected', 'cloudflare'],
        "crap_similarity_threshold": .25,

        # image processing
        "image_min_size": (300, 200),
        "image_brisque_max_score": get_env('image_brisque_max_score', 50),
        "image_brisque_ignore_exception": True,

        # edits version pipeline (cf. CheckEdits)
        "edits_new_version_fields": (TITLE, KEYWORDS),
        "edits_pristine_threshold": .8,
        "edits_new_version_threshold": .7,

        # COMMANDS
        # =============================================================================================
        # `scrapy nlp <sum|meta> -t ` -t siblings=.4 -t related=.3 -d <day>
        #
        # similarity_max_docs: most similar docs count to return
        "similarity_siblings_threshold": .2,
        "similarity_related_threshold": .1,
        "similarity_max_docs": 2,
    }

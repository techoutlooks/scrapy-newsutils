from collections import OrderedDict
from itemadapter import ItemAdapter

from daily_query.mongo import Collection
from newsutils.helpers import get_env_variable
from newsutils.appsettings import AppSettings
from ..fields import *


# defaults for computed field names as
# populated/persisted by the `NlpDaily` util class
_NLP_BASE_FIELDS_CONF = {

    # summarization
    "CATEGORY_FIELD": "category",
    "CAPTION_FIELD": "caption",
    "SUMMARY_FIELD": "summary",

    # similarity
    "SIBLINGS_FIELD": "siblings",
    "RELATED_FIELD": "related",
}


# defaults for configurable fields
# TODO?: prefix with `DEFAULT_` ??
# FIXME: make `ITEM_ID_FIELD`, `NLP_FIELDS` lazily loaded
#       since they depend on other dynamics settings.
_DB_ID_FIELD = "_id"
_ITEM_ID_FIELD = SHORT_LINK


class Posts(AppSettings):
    """
    Default settings for the posts scraper
    """

    LOGGING = False

    LOG_FORMATTER = 'scrapy.logformatter.LogFormatter'

    ITEM_PIPELINES = {
        'newsutils.pipelines.FilterDate': 100,
        'newsutils.pipelines.CheckEdits': 110,
        'newsutils.pipelines.DropLowQualityImages': 120,
        'newsutils.pipelines.SaveToDb': 300
    }

    # TODO: replace MongoDB with CouchDB
    # MongoDB only is supported. This is temporary.
    # BasePipeline's `get_setting` raises an exception if settings are not defined.
    CRAWL_DB_URI = 'mongodb://localhost:27017/scraped_news_db'

    # DB_ID_FIELD: row id from the database engine
    DB_ID_FIELD = _DB_ID_FIELD

    BRANDING = {
        "BOT_IMAGE_URL": None,
        "LOGO_URL": None
    }

    POSTS = {

        "DEFAULT_LANG": "en",

        # POST
        # =============================================================================================
        # per-post editable/computed fields values.

        "AUTO_PUBLISH": True,
        "ITEM_ID_FIELD": _ITEM_ID_FIELD,
        **_NLP_BASE_FIELDS_CONF,


        # NLP
        # =============================================================================================
        # section defines inputs to the NLP strategy that runs nlp tasks
        # **strategy** : decision made by the `nlp.py` module based on below inputs
        # **tasks** : `similarity`, `summary`, `metapost` generation.
        # NLP_USES_META: also add metaposts (type==META_POST) as inputs to NLP tasks?
        # SUMMARY_USES_NLP: (iff !metapost type), use text from `excerpt` field instead of `text` field?
        # META_USES_NLP: metapost generation: use text from `caption` field instead of `title` field?
        "NLP_USES_META": False,
        "SUMMARY_USES_NLP": False,
        "META_USES_NLP": True,


        # PIPELINES
        # =============================================================================================
        # Following settings control management of post pipelines
        #
        # ITEM_ID_FIELD: NOT the database id. yields unique posts accurately for handling by the
        #       `.process_post()` pipeline fn
        # DB_ID_FIELD: the database id
        # IMAGE_MIN_SIZE: images should be at least 200x150 px to save to db
        # AUTO_PUBLISH: controls the`.is_draft` state of newly created posts
        #       if True (the default), hints that the post is created in its final version once for all.
        # IMAGE_BRISQUE_IGNORE_EXCEPTION: defaults to disregard image quality inspection on error.
        # EDITS_NEW_VERSION_FIELDS: fields whose values changes suggest a new post version
        #       subsequently increased by the `CheckEdits` pipeline
        # EDITS_EXCLUDED_FIELDS: computed fields, post version checks should not account for their values,
        #       since they are dynamic.

        # dynamic field names defaults
        "IMAGE_MIN_SIZE": (300, 200),
        "IMAGE_BRISQUE_MAX_SCORE": get_env_variable('IMAGE_BRISQUE_MAX_SCORE', 50),
        "IMAGE_BRISQUE_IGNORE_EXCEPTION": True,
        "EDITS_NEW_VERSION_FIELDS": (TEXT, TITLE),


        # COMMANDS
        # =============================================================================================
        # `scrapy nlp <sum|meta> -t ` -t siblings=.4 -t related=.3 -d <day>
        #
        # SIMILARITY_MAX_DOCS: most similar docs count to return
        "SIMILARITY_SIBLINGS_THRESHOLD": .4,
        "SIMILARITY_RELATED_THRESHOLD": .2,
        "SIMILARITY_MAX_DOCS": 2,
    }


def patch_scrapy_settings():
    """
    Merges app settings with scrapy settings,
    Patches stdlib imports for both the scrapy project settings `crawler.settings`, and
    the default settings `scrapy.settings.default_settings`,

    :return merged settings dict.
    """

    # inject app-defined settings (`Posts`) inside the Scrapy settings,
    # (both project and default) existing settings taking precedence.
    settings = Posts()('crawler.settings', 'scrapy.settings.default_settings')

    # == [ COMPUTED SETTINGS] ==
    # load `computed` settings dynamically from env_vars, settings.py
    # `editable` settings are typically computed based on other configurable settings
    posts_config = settings.config


    posts_config["NLP_BASE_FIELDS"] = \
        [posts_config[f] for f in list(_NLP_BASE_FIELDS_CONF)]


    posts_config["NLP_FIELDS"] = \
         posts_config["NLP_BASE_FIELDS"] + \
         [TAGS, KEYWORDS, EXCERPT]

    posts_config["COMPUTED_FIELDS"] = \
        [settings["DB_ID_FIELD"]] + \
        posts_config["NLP_BASE_FIELDS"] + [posts_config[f] for f in (
            'ITEM_ID_FIELD',
        )]

    posts_config["EDITS_EXCLUDED_FIELDS"] = [
        VERSION,
        settings["DB_ID_FIELD"],
        posts_config["ITEM_ID_FIELD"],
        *posts_config["NLP_FIELDS"],
    ]

    return settings.settings


_settings = None

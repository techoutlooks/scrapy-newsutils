from .funcs import get_env_variable
from newsutils.bots.appsettings import AppSettings


# immutable Post field names
# these fields are NOT configurable
TEXT = "text"
EXCERPT = "excerpt"
TITLE = "title"
TAGS = "tags"
KEYWORDS = "keywords"
SHORT_LINK = "short_link"
TYPE = "type"
PUBLISH_TIME = "publish_time"
MODIFIED_TIME = "modified_time"
TOP_IMAGE = "top_image"
IMAGES = "images"
VIDEOS = "videos"
COUNTRY = "country"
AUTHORS = "authors"
IS_DRAFT = "is_draft"
IS_SCRAP = "is_scrap"
VERSION = "version"
PAPER = "paper"

SCORE = "score"


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


#
META_POST = 'metapost'      # meta post type
UNKNOWN = "N/A"         # unknown values


# defaults for configurable fields
# TODO?: prefix with `DEFAULT_` ??
# FIXME: make `ITEM_ID_FIELD`, `NLP_FIELDS` lazily loaded
#       since they depend on other dynamics settings.
_DB_ID_FIELD = "_id"
_ITEM_ID_FIELD = SHORT_LINK


class Posts(AppSettings):

    LOGGING = False

    LOG_FORMATTER = 'bots.logformatter.LogFormatter'

    ITEM_PIPELINES = {
        'bots.pipelines.FilterDate': 100,
        'bots.pipelines.CheckEdits': 110,
        'bots.pipelines.DropLowQualityImages': 120,
        'bots.pipelines.SaveToDb': 300
    }

    # TODO: replace MongoDB with CouchDB
    # MongoDB only is supported. This is temporary.
    # BasePipeline's `get_setting` raises an exception if settings are not defined.
    CRAWL_DB_URI = 'mongodb://localhost:27017/scraped_news_db'

    BRANDING = {
        "BOT_IMAGE_URL": None,
        "LOGO_URL": None
    }

    POSTS = {

        "DEFAULT_LANG": "en",

        # POST
        # =============================================================================================
        # per-post editable/computed fields values.

        # DB_ID_FIELD: row id from the database engine
        "AUTO_PUBLISH": True,
        "DB_ID_FIELD": _DB_ID_FIELD,
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
        "SIMILARITY_RELATED_THRESHOLD": 2,
        "SIMILARITY_MAX_DOCS": 2,
    }





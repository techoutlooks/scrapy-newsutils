import enum


# Common settings
# used by all packages.
# -----------------------------------

UNKNOWN = "N/A"                             # unknown values


# Package/feat `crawl`
# -----------------------------------

# immutable `Post` field names
# these fields are NOT configurable
TEXT = "text"
EXCERPT = "excerpt"
TITLE = "title"
TAGS = "tags"
KEYWORDS = "keywords"
SHORT_LINK = "short_link"
LINK_HASH = "link_hash"
LINK = "link"
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

# nlp
SCORE = "score"
METAPOST = 'metapost'                       # meta post type


# Package/feat `publish`
# -----------------------------------

# stats, a  DxM statistic,
# ie. a per-network collection of metrics
NETWORKS = "networks"
DIMENSIONS = "dimensions"
METRICS: str = "metrics"

# Database fields
COLLECTION = "collection"
NETWORK = "network"
DIMENSION = "dimension"


# Scrapy commands
# -----------------------------------

# args seperator in `scrapy publish <args-string-list>`
# for destructuring scrapy cmd's arguments string list
# eg. scrapy publish facebook,instagram,twitter
ARGS_SEP = ","


class TaskTypes(enum.Enum):
    """
    Task types run by Scrapy commands
    """
    CRAWL_ALL = 'crawlall'  # eg. scrapy crawlall ...
    NLP = "nlp"             # eg. scrapy nlp [similarity|summary|metapost] ...


USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:78.0) Gecko/20100101 Firefox/78.0'


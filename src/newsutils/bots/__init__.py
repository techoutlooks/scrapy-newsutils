from .funcs import add_fullstop
from .default_settings import Posts, \
    TITLE, TEXT, TAGS, KEYWORDS, EXCERPT, VERSION, _NLP_BASE_FIELDS_CONF

# inject app-defined settings (`Posts`) inside the Scrapy settings,
# (both project and default) existing settings taking precedence.
settings = Posts()('settings', 'scrapy.settings.default_settings')


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
    posts_config["NLP_BASE_FIELDS"] + \
    [posts_config[f] for f in (
        'ITEM_ID_FIELD', 'DB_ID_FIELD'
    )]

posts_config["EDITS_EXCLUDED_FIELDS"] = [
    VERSION,
    *posts_config["NLP_FIELDS"],
    posts_config["DB_ID_FIELD"],
    posts_config["ITEM_ID_FIELD"],
]


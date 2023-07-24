from default_settings import *


# scrapy
# ======

LOG_FORMATTER = 'logformatter.LogFormatter'

ITEM_PIPELINES = {
    'pipelines.posts.FilterDate': 100,
    'pipelines.posts.CheckEdits': 110,
    'pipelines.posts.DropNoqaImages': 120,
    'pipelines.posts.SaveToDb': 300,
}

COMMANDS_MODULE = 'commands'


# overrides
# =========

POSTS = {
    "SIMILARITY_SIBLINGS_THRESHOLD": 0.3,
    "SIMILARITY_RELATED_THRESHOLD": 0.15,
}

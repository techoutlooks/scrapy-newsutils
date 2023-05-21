from daily_query.mongo import MongoDaily
from scrapy.commands import ScrapyCommand

from newsutils.conf.mixins import PostConfigMixin


__all__ = ("DayCmd", )


class DayCmd(PostConfigMixin, ScrapyCommand):
    """
    Base command for tasks that run daily.
    TODO: implement, then refactor code in newsbot.crawl.commands
    """

    # db handle
    daily = MongoDaily(PostConfigMixin.db_uri)


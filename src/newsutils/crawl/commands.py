import os

import psutil
from daily_query.mongo import MongoDaily
from scrapy.commands import ScrapyCommand

from newsutils.conf.mixins import PostConfigMixin

__all__ = ("DayCmd",)

from newsutils.exceptions import ImproperlyConfigured


class Cmd(PostConfigMixin, ScrapyCommand):

    @property
    def name(self):
        *_, n = type(self).__module__.rsplit('.', 1)
        return n

    @property
    def log_prefix(self):
        """ This is picked up by the logger. cf `LoggingMixin`. """
        return self.name

    def is_running(self) -> psutil.Process:
        """ whether another instance of the command is running already """
        for proc in psutil.process_iter():
            try:
                # search command line of any process
                # but ignore self process
                if f"scrapy {self.name.lower()}" in ' '.join(proc.cmdline()).lower() \
                        and proc.pid != os.getpid():
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None


class DayCmd(Cmd):
    """
    Base command for tasks that run daily.
    TODO: implement, then refactor code in newsbot.crawl.commands
    """

    daily = MongoDaily(PostConfigMixin.db_uri)  # db handle

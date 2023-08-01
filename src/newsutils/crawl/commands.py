import os
from copy import deepcopy

import psutil
from daily_query.mongo import MongoDaily
from scrapy.commands import ScrapyCommand

from newsutils.conf import configure_posts
from newsutils.conf.mixins import PostConfigMixin

__all__ = ("PostCmd", "DayCmd",)

from newsutils.exceptions import ImproperlyConfigured


class PostCmd(PostConfigMixin, ScrapyCommand):
    """ Post-aware command for buidling smart tasks. """

    @property
    def name(self):
        *_, n = type(self).__module__.rsplit('.', 1)
        return n

    @property
    def log_prefix(self):
        """ This is picked up by the logger. cf `LoggingMixin`. """
        return self.name

    def is_running(self) -> psutil.Process:
        """ Whether another instance of this command is already running. """
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

    def set_post_settings(self, params: dict):
        """ Merge params into `settings.POSTS` """
        s = deepcopy(self.settings['POSTS'])
        s.update(params)
        configure_posts({'POSTS': dict(s)}, priority='cmdline')
        self.settings.set('POSTS', s, priority='cmdline')


class DayCmd(PostCmd):
    """
    Base command for tasks that run daily.
    TODO: implement, then refactor code in newsbot.crawl.commands
    """

    daily = MongoDaily(PostConfigMixin.db_uri)  # db handle


import inspect
import traceback
import warnings
from typing import Iterable

import scrapy
from daily_query.mongo import Collection
from itemadapter import ItemAdapter
from scrapy.spiderloader import SpiderLoader

from newsutils.crawl import BasePostCrawler, PostCrawlerContext
from newsutils.helpers import to_camel
from newsutils.logging import LoggingMixin


def create_post_crawler_class(ctx):
    attrs = ItemAdapter(PostCrawlerContext(ctx)).asdict()
    name = to_camel(attrs['name'])
    return type(name, (BasePostCrawler,), attrs)


def iter_spider_classes(contexts):
    """Return an iterator over all spider classes defined in the given module
    that can be instantiated (i.e. which have name).

    :param Iterable[PostCrawlerContext] contexts:
    """
    # this needs to be imported here until get rid of the spider manager
    # singleton in scrapy.spider.spiders

    for ctx in contexts:
        obj = create_post_crawler_class(ctx)
        if (
                inspect.isclass(obj)
                and issubclass(obj, BasePostCrawler)
                and getattr(obj, 'name', None)
        ):
            obj.__module__ = __name__
            yield obj


class DatabaseSpiderLoader(LoggingMixin, SpiderLoader):
    """
    Adds ability to generate spider classes dynamically
    from configuration loaded from the database.
    https://docs.scrapy.org/en/latest/topics/api.html#topics-api-spiderloader
    """

    def __init__(self, settings):
        self.settings = settings
        super().__init__(settings)

    def _load_all_spiders(self):

        # default, loads spiders from `settings.SPIDER_MODULES`
        super()._load_all_spiders()

        # loads spiders from the db
        try:
            contexts = self._load_contexts()
            for spcls in iter_spider_classes(contexts):
                self._found[spcls.name].append((spcls.__module__, spcls.__name__))
                self._spiders[spcls.name] = spcls
        except Exception:
            if self.warn_only:
                warnings.warn(
                    f"\n{traceback.format_exc()}Could not load spiders from database. "
                    "See above traceback for details.",
                    category=RuntimeWarning)
            else:
                raise

        # checks dupes across both modules and the db
        self._check_name_duplicates()

    def _load_contexts(self) -> Iterable[PostCrawlerContext]:
        """ Loads contexts from the database required
        to construct spiders classes dynamically.

        Set `.version` field to integer `0` to disable a spider,
        otherwise loads latest version of any spider.
        """
        try:
            db_collection = Collection(
                self.settings['CRAWL_DB_SPIDERS'],
                db_or_uri=self.settings["CRAWL_DB_URI"]
            )
            for ctx in db_collection.find({'version': {'$nin': [0]}}).sort('version', -1):
                yield PostCrawlerContext(ctx)
        except Exception as e:
            self.log_error(
                f'error loading initializer context '
                f'from database collection {db_collection.name} @ {db_collection.db.name} '
                f'for spider of type `BasePostCrawler` ', str(e)
            )
            raise

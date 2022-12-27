import abc

from scrapy.exceptions import DropItem

from daily_query.mongo import PyMongo
from daily_query.helpers import mk_datetime

from ...logging import PADDING
from .items import Post
from .posts import Day, PostConfigMixin


__all__ = [
    "PipelineMixin", "BasePostPipeline",
    "BaseMongoPipeline",
]


class PipelineMixin(PostConfigMixin):
    """
    Foundational block for building pipelines
    """

    stats = dict(total=0, ok=0)

    def open_spider(self, spider):
        self.spider = spider


class BaseMongoPipeline(PyMongo, PipelineMixin, abc.ABC):
    """
    Basic pipeline for saving scraped items to a custom Mongo db collection.
    The said collection name is calculated dynamically; eg. patterned after
    the currently being processed item's attributes (`process_item`).

    Start Mongodb first:
        upward/db/docker-compose.yml
        docker-compose up -d
    """

    def __init__(self, db_uri):
        super().__init__(db_uri)

    @abc.abstractmethod
    def get_collection_name(self):
        pass

    @property
    def collection(self):
        return self.db[self.get_collection_name()]

    @classmethod
    def from_crawler(cls, crawler):
        return cls(mongo_uri=cls.db_uri)

    def close_spider(self, spider):
        self.db.client.close()

    @abc.abstractmethod
    def process_item(self, item, spider):
        """ Default implementation. """
        pass

    # def save(self, item):
    #     """ Tries to fetch an object from database based on the given **filter**.
    #     If a match is found, it updates the fields passed in the **item** dictionary.
    #     Creates a new post if item has no id """
    #
    #     adapter = ItemAdapter(item)
    #     item_id = item.get(self.db_id_field, ObjectId())
    #     adapter.update({self.db_id_field: item_id})
    #
    #     return self.collection.update_one(
    #         {'_id': {'$eq': item_id}}, {"$set": adapter.asdict()}, upsert=True)


class BasePostPipeline(PipelineMixin, abc.ABC):
    """
    Factory for creating generic item pipelines that handle `Post` items.
    Introduces:

    - Scrapy Item -> `Post` instance conversion
    - post validation via `.is_valid()`
    - `.process_post()` to use instead of Scrapy's regular `.process_item()`.
    - `.post_time` datetime attribute set with published time of post
            used feg. to save post in a collection named after the post date
    - readiness for **daily** database operations on posts; eg.:
        `get.day.search()`, `.day.update_or_create()

    # ??? delete:
    Use exclusively for extending `BasePipeline` subclasses,
    since the mixin relies on members inside `BasePipeline`.

    """

    # Instance members. Set with each new `process_item()` request
    # sent by a spider to the item pipeline. Defined outside `init()` for the mixin
    # not to override the base implementation; eg. class(SavePostMixin, BaseMongoPipeline)
    spider = None
    day = None
    post = None
    errors = []
    post_time = None

    def process_item(self, item, spider):
        """
        Use `process_post()` instead for processing `Post` items. This enables :
        - running basic checks and cleanup before returning control to `process_post`
        - setting `.post` and `.post_time` for a valid item
        - dropping an invalid item.
        """

        self.spider = spider

        # drop item is not a `Post` else
        # set post instance and time available.
        if not self.is_valid(item):
            self.log_ok(f'Dropping invalid post: {item["short_link"]}. '
                        f'Errors: {self.errors}')
            raise DropItem("invalid post")
        else:
            self.post = item
            self.post_time = mk_datetime(item.get('publish_time'))
            # FIXME: don't init a Day() and read entire collection that
            #   possible changed every time a pipeline is loaded !
            self.day = self.get_day()
            return self.process_post()

    def is_valid(self, item):
        """
        Runs post validation and set `.errors` status
        """

        self.errors = []  # reset

        if not item or not len(item):
            self.errors.append('Item in pipeline is empty')
        if not isinstance(item, Post):
            self.errors.append('Item in pipeline is not a `Post`')
        if not item['publish_time']:
            self.errors.append('Item has no `publish_time`')

        # run custom validation, ie. method `.validate()` if avails
        # it is expected to raise
        try:
            if hasattr(self, 'validate'):
                getattr(self, 'validate')(item)
        except Exception as e:
            self.errors.append(str(e))

        return not bool(self.errors)

    def get_day(self):
        """ Daily collection the current post will be saved under. """
        return Day(str(self.post_time.date()))

    @abc.abstractmethod
    def process_post(self):
        """ Implementation must return post item to the next pipeline. """
        pass







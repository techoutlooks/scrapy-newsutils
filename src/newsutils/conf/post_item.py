import scrapy
from itemadapter import ItemAdapter
from scrapy.item import ItemMeta

from .constants import METAPOST, TYPE
from .globals import get_setting
from .utils import ItemValue, Item


__all__ = (
    "Post", "PostMeta",
    "mk_post", "defaultpost"
)


# ==[ POST ]==

class PostMeta(ItemMeta):
    """
    Metaclass for creating a `Post` Item class
    with configurable fields (user-editable names).
    """

    def __new__(mcs, class_name, bases, attrs):

        # adds user-defined attributes to Post item
        new_attrs = {f: scrapy.Field() for f in get_setting('POSTS.COMPUTED_FIELDS')}
        new_attrs.update(attrs)
        return super().__new__(mcs, class_name, bases, new_attrs)


defaultpost = ItemValue(ItemValue.NO_DEFAULT, {
    "version": 1,
    "title": "",
    "text": "",
    "excerpt": "",

    # not guessed are plural fields by heuristic
    # cf. `ItemValue.is_plural()`
    "related": []
})


class Post(Item, metaclass=PostMeta):
    """
    With computed fields by `Post` aware pipelines
    """
    country = scrapy.Field()
    link = scrapy.Field()
    short_link = scrapy.Field()
    link_hash = scrapy.Field()
    type = scrapy.Field()
    title = scrapy.Field()
    text = scrapy.Field()
    excerpt = scrapy.Field()
    publish_time = scrapy.Field()
    modified_time = scrapy.Field()
    top_image = scrapy.Field()
    images = scrapy.Field()
    videos = scrapy.Field()
    authors = scrapy.Field()
    keywords = scrapy.Field()
    tags = scrapy.Field()

    paper = scrapy.Field()
    version = scrapy.Field()
    is_draft = scrapy.Field()
    is_scrap = scrapy.Field()

    @property
    def is_meta(self):
        return self[TYPE].startswith(METAPOST)

    def asdict(self):
        item = ItemAdapter(self).asdict()
        item['id'] = str(item[get_setting("DB_ID_FIELD")])
        del item[get_setting("DB_ID_FIELD")]
        return item


# creates a post with default values
# mk_defaultpost = lambda: Post(defaults=defaultpost)
mk_post = lambda *args, **kwargs: Post(*args, defaults=defaultpost, **kwargs)

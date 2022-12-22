import collections

import scrapy
from scrapy.item import ItemMeta

from newsutils.bots import settings


# basic field type detection heuristic from field names that
# follow naming conventions: is_* -> bool, *s -> plural, etc.
from newsutils.bots.default_settings import META_POST, TYPE

is_plural = lambda w: w.endswith('s') and not w.endswith('ss')
is_bool = lambda w: w.startswith('is_')


class ItemValue(collections.UserDict):
    """
    Provider for values to be set on the `scrapy.Item` instances,
    Impl. as a dict container in similar manner as `collections.defaultdict`,
    but able to initialize default values by guessing their resp. key type,
    ie.
        pluralized key (eg. 'authors') ->  initialized to []
        key starting with `is_` (eg. 'is_draft') -> bool, initialized to False

    Priority for resolving values :
        inventory -> heuristics -> default_factory -> raises KeyError
    """

    # behavior if the builtin heuristics find no default value for any given field
    # `NO_DEFAULT`: return `None` if no default was found for the field
    # `REQUIRES_DEFAULT`: raises KeyError is no default was found for the key
    NO_DEFAULT = lambda: None
    REQUIRES_DEFAULT = None

    def __init__(self, default_factory=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not callable(default_factory) and default_factory is not None:
            raise TypeError('first argument must be callable or None')
        self.default_factory = default_factory

    def __missing__(self, key: str):
        if self.default_factory is None:
            raise KeyError(key)

        if key not in self:
            if is_plural(key):
                self[key] = []
            elif is_bool(key):
                self[key] = False
            else:
                self[key] = self.default_factory() if \
                    self.default_factory else None

        return self[key]


class Item(scrapy.Item):
    """ Enhanced Item
        - Supports setting default values for scrapy fields,
    """
    def __init__(self, *args, defaults: ItemValue = None, **kwargs):
        super().__init__(*args, **kwargs)

        # set default values for all fields
        if defaults:
            for n in list(self.fields):
                if isinstance(self.fields[n], scrapy.Field):
                    self[n] = self.get(n, defaults[n])


# ==[ AUTHOR ]==


class Author(Item):

    name = scrapy.Field()
    profile_image = scrapy.Field()
    role = scrapy.Field()


botauthor = ItemValue(ItemValue.NO_DEFAULT, {
    "name": "Rob. O.",
    "profile_image": settings['POSTS']['BRAND']['BOT_IMAGE_URL'],
    "role": "NLP",
})


# AriseNews paper
BOT = Author(defaults=botauthor)


# ==[ PAPER ]==


class Paper(Item):

    brand = scrapy.Field()
    description = scrapy.Field()
    logo_url = scrapy.Field()


thispaper = ItemValue(ItemValue.NO_DEFAULT, {
    "brand": "ARISEnews",
    "description": "Arise, Shine !",
    "logo_url": settings['POSTS']['BRAND']['LOGO_URL']
})

# AriseNews paper
THIS_PAPER = Paper(defaults=thispaper)


# ==[ POST ]==


class PostMeta(ItemMeta):
    """
    Customizes `Post` item class, eg.:
    - from configurable Post fields.
    """

    def __new__(mcs, class_name, bases, attrs):

        # adds user-defined attributes to Post item
        new_attrs = {f: scrapy.Field() for f in settings['POSTS']['COMPUTED_FIELDS']}
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
        return self[TYPE].startswith(META_POST)


# creates a post with default values
# mk_defaultpost = lambda: Post(defaults=defaultpost)
mk_post = lambda *args, **kwargs: Post(*args, defaults=defaultpost, **kwargs)









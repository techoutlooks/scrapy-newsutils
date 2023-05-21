import scrapy
from scrapy.utils.project import get_project_settings

from newsutils.conf.utils import ItemValue, Item


__all__ = [
    "ItemValue", "Author", "Paper",
    "BOT", "THIS_PAPER",
]


settings = get_project_settings()


# ==[ AUTHOR ]==


class Author(Item):

    name = scrapy.Field()
    profile_image = scrapy.Field()
    role = scrapy.Field()


botauthor = ItemValue(ItemValue.NO_DEFAULT, {
    "name": "Rob. O.",
    "profile_image": settings['BRANDING']['bot_image_url'],
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
    "logo_url": settings['BRANDING']['logo_url']
})

# AriseNews paper
THIS_PAPER = Paper(defaults=thispaper)










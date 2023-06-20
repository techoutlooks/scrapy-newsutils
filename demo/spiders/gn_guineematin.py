from newsutils.crawl.spiders import BasePostCrawler


class GnGuineeMatin(BasePostCrawler):
    """
    # scrapy crawl gn-guineematin -O gn-guineematin.json
    """

    # by `scrapy.spider.Spider`
    name = 'gn-guineematin'
    allowed_domains = ['guineematin.com']
    start_urls = ['https://guineematin.com/']

    # by `newsutils.scrapy.base.spiders.NewsSpider`
    country_code = 'GN'
    language = 'fr'
    rule_sets = {
        "featured": {
            "text": ".//*[@id=\"tdi_75\"]//a",
            "images": "//figure/img/@src"
        },
        "default": {
            "text": ".//*[contains(concat(\" \",normalize-space(@class),\" \"),\" tdi_127 \")]//a",
            "images": "//figure/img/@src"
        },
    }

    # crawl only specific dates
    # days_from = '2022-04-19'
    # days_to = '2022-04-25'
    # days = ['2022-04-12', '2022-04-09']



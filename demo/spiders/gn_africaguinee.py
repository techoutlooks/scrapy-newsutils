from newsutils.crawl.spiders import BasePostCrawler


class GnAfricaGuinee(BasePostCrawler):
    """

    # scrapy crawl gn-africaguinee -O gn-africaguinee.json
    """

    # by `scrapy.spider.Spider`
    name = 'gn-africaguinee'
    allowed_domains = ['africaguinee.com']
    start_urls = ['https://www.africaguinee.com/']

    # by `newsutils.scrapy.base.spiders.NewsSpider`
    country_code = 'GN'
    language = 'fr'
    post_images = "//figure/img/@src"
    rule_sets = {
        "featured": {
            "text": ".//*[contains(concat(\" \",normalize-space(@class),\" \"),\" post-slider-link \")]",
            "images": ".//*[contains(concat(\" \",normalize-space(@class),\" \"),\" img-article-details \")]//@src"
        },
        "default": {
            "text": ".//*[contains(concat(\" \",normalize-space(@class),\" \"),\" post-link \")]",
            "images": ".//*[contains(concat(\" \",normalize-space(@class),\" \"),\" img-article-details \")]//@src"
        },
    }

    # days_from = '2022-04-19'
    # days_to = '2022-04-25'
    # days = ['2022-04-12', '2022-04-09']





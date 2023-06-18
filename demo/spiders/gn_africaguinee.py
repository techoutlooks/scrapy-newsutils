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
    post_texts = {
        "featured": '//*[contains(concat( " ", @class, " " ), concat( " ", "views_slideshow_pager_field_item", " " ))]//a',
        "default": '//*/div/div/div/div/div/h3//a',
    }

    # days_from = '2022-04-19'
    # days_to = '2022-04-25'
    # days = ['2022-04-12', '2022-04-09']





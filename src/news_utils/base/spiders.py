import abc

import nltk
import pycountry

from newspaper import Article, build
from scrapy.spiders import Rule, CrawlSpider
from scrapy.linkextractors import LinkExtractor

from .items import Post, Author, Paper
from news_utils.base.logging import LoggingMixin, \
    FAILED, OK, PADDING
from news_utils.default_settings import TYPE
from news_utils.logo import parse_logo
from daily_query.helpers import parse_dates


nltk.download('punkt')


# default post types
DEFAULT_POST = "default"
FEATURED_POST = "featured"


class PostCrawlerMeta(abc.ABCMeta):
    """
    Custom post crawler
    https://realpython.com/python-metaclasses/
    https://www.geeksforgeeks.org/__new__-in-python/
    """

    def __new__(cls, *args, **kwargs):
        crawler = super().__new__(cls, *args, **kwargs)
        # dynamic crawl_all rules:
        # hooking `.from_crawler()`, so that base's Spider._set_crawler() gets a
        # chance to initialise `.settings` and connect the `spider_closed` signal
        # https://stackoverflow.com/a/27514672, https://stackoverflow.com/a/25352434
        crawler.rules = [
            Rule(LinkExtractor(restrict_xpaths=[xpath]),
                 callback='parse_post',
                 cb_kwargs={TYPE: key},
                 follow=False)
            for (key, xpath) in crawler.post_types_xpaths.items()
            if crawler.post_types_xpaths[key]
        ]
        return crawler


class PostCrawlerMixin(LoggingMixin):
    """
    Generic (abstract) articles spider.
    Attributes here are re-used extensively by post pipelines,
    ie., PostMixin subclasses.

    #TODO: improved topic modeling through (LDA, LSTM?).
        `post.keywords` does mere word frequency analysis.
    """

    # custom props
    # nota: will get overridden by `init()` kwargs
    country_code = None         # Alpha‑2 ISO 3166 country code
    language = None             # language of post

    # below date specs will get parsed into `filter_dates`,
    # a list of days to consider for crawling.
    days_from: str = None            # crawl_all posts published at least since `days_from`.
    days_to: str = None              # crawl_all posts published at most  `days_to`;  today if None.
    days: [str] = []                   # single dates

    # pull posts from pages links extracted in turn by below xpaths only.
    # default, featured: XPath to resp. regular, featured posts
    # https://devhints.io/xpath
    post_types_xpaths = {
        FEATURED_POST: None,
        DEFAULT_POST: None,
    }

    # per post
    post_images_xpath = None

    def prepare(self, *args, days={}, **kwargs):
        """

        :param args:
        :param days:
        :param kwargs:
        :return:
        """
        # FIXME: should pop cmdline opts from kwargs? eg. 'from', 'to'

        # required fields
        assert self.country_code, "`country_code` (ISO 3166-1) field required"
        assert self.post_types_xpaths, "`post_types_xpaths` field required"

        # clean user input, set defaults
        # cmdline args (kwargs) have priority over class attributes!
        self.days = days.get('days', self.days)
        self.days_from = days.get('days_from', self.days_from)
        self.days_to = days.get('days_to', self.days_to)

        if not self.language:
            self.language = self.settings["POSTS"]['DEFAULT_LANG']

        # compute filter dates for crawling
        self.filter_dates = parse_dates(
            days_from=self.days_from, days_to=self.days_to,
            days=self.days,
        )

    @property
    def country(self):
        """ Country object from country code """
        return pycountry.countries.get(alpha_2=self.country_code)

    def get_authors(self, article: Article, response=None):
        """ Articles authors. """
        return list(map(lambda name: Author(
            name=name, profile_image="", role=""
        ), article.authors))

    def parse_post(self, response, type) -> Post:

        a = Article(response.url)
        a.download()
        a.parse()

        # required to parse summary, keywords, etc.
        # FIXME: set NLP language to that of post
        #   based on the scraper's country, language props.
        a.nlp()

        short_link = a.url.replace(a.source_url, '')
        images, top_image = self.parse_post_images(response, a)
        self.log_info(f"{OK:<{PADDING}}" 
                      f"parsing (%d/%d) image(s) for post {short_link}"
                      % (len(images), len(list(a.images))))

        post = Post(
            country=self.country.alpha_2,
            link=a.url,
            short_link=short_link,
            title=a.title,
            text=a.text,
            excerpt=a.summary,
            publish_time=str(a.publish_date) if a.publish_date else None,
            modified_time=a.meta_data["post"].get("modified_time"),
            top_image=top_image,
            images=images,
            videos=a.movies,
            authors=self.get_authors(a, response),
            keywords=list(a.keywords),
            tags=list(a.tags),
            link_hash=a.link_hash,
            type=type,

            # computed fields
            # setting initial values
            version=1,
            is_scrap=True,
            is_draft=not self.settings["POSTS"]['AUTO_PUBLISH']
        )

        self.log_info(f'{OK:<{PADDING}}' 
                      f'parsing {type} post {post["short_link"]}')
        return post

    def parse_post_images(self, response, article3k):
        """
        Improved images url parsing vs `newspaper` module
        Not all images intermeddled with a post content (eg. interstitial ads)
        are relevant to that post...

        #TODO: move to pipeline?  burden of image parsing if the post
            might be later deleted by the `DropLowQualityImages`
        """
        images = []
        if self.post_images_xpath:
            try:
                images = response.xpath(self.post_images_xpath).extract()
            except ValueError as e:
                self.log_info(f'{FAILED:<{PADDING}}{self.post_images_xpath}')
                self.log_debug(str(e))

        images = images or list(article3k.images)
        top_image = images[0] if images else article3k.top_image
        return images, top_image


class BasePostCrawler(PostCrawlerMixin, CrawlSpider, metaclass=PostCrawlerMeta):
    """
    Generic (abstract) online news source-aware spider.
    `Sources are abstractions of online news vendors like huffpost or cnn`

    Enables associated pipelines (??) to also link posts
    with their corresponding news source (paper).
    """

    _paper = None

    def __init__(self, *args, **kwargs):

        self.prepare(*args, **kwargs)
        self.source = build(self.start_urls[0], language=self.language)
        super().__init__(*args, **kwargs)

    def get_paper(self, response):
        """ Return the cached paper instance if available
        Avoids recomputing paper on each `parse_post` request.
        """
        if not self._paper:
            self._paper = Paper(
                brand=self.source.brand,
                description=self.source.description,
                logo_url=self.source.logo_url or self.parse_logo(response)
            )
        return self._paper

    def get_recent_posts(self) -> [Article]:
        """ Override. Recently published posts
        Defaults to `newspaper.articles` """

        return self.source.articles

    def parse_logo(self, response) -> str:
        """ Returns the newspaper's logo url. """

        imgs = parse_logo(response)["img_url_list"]
        logo, status = (imgs[0], OK) if imgs \
            else (None, FAILED)

        self.log_info(f"{status:<{PADDING}}" 
                      f"parsing site logo (out of {len(imgs)} images)")
        self.log_debug(str(logo))

        return logo

    def parse_post(self, response, type) -> Post:
        """ Override. Links newspaper with post. """

        post = super().parse_post(response, type)
        post["paper"] = self.get_paper(response)
        return post



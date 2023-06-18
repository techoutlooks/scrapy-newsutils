import abc
from typing import Mapping

import nltk
import pycountry
import scrapy
from lxml.etree import XPath
from scrapy.item import ItemMeta

from newsutils.logging import LoggingMixin, FAILED, OK, PADDING
from newsutils.logo import parse_logo
from daily_query.helpers import parse_dates

from scrapy.spiders import Rule, CrawlSpider
from scrapy.linkextractors import LinkExtractor

from newspaper import Article, build

from .items import Author, Paper
from newsutils.conf.post_item import Post, mk_post
from newsutils.conf import TYPE, get_setting

nltk.download('punkt')


__all__ = [
    "PostCrawlerMeta", "PostCrawlerMixin", "BasePostCrawler", "PostCrawlerContext",
    "DEFAULT_POST", "FEATURED_POST"
]


# default post types
DEFAULT_POST = "default"
FEATURED_POST = "featured"


class PostCrawlerMeta(abc.ABCMeta):
    """
    Sets crawl rules dynamically based on the `.post_texts` classproperty.
    https://realpython.com/python-metaclasses/
    https://www.geeksforgeeks.org/__new__-in-python/
    """

    def __new__(cls, *args, **kwargs):
        crawler = super().__new__(cls, *args, **kwargs)
        # dynamic crawl_all rules:
        # hooking `.from_crawler()`, so that crawl's Spider._set_crawler() gets a
        # chance to initialise `.settings` and connect the `spider_closed` signal
        # https://stackoverflow.com/a/27514672, https://stackoverflow.com/a/25352434

        crawler.rules = [
            Rule(LinkExtractor(restrict_xpaths=[xpath]),
                 callback='parse_post',
                 cb_kwargs={TYPE: key},
                 follow=False)
            for (key, xpath) in crawler.post_texts.items()
            if crawler.post_texts[key]
        ]
        return crawler


class PostCrawlerMixin(LoggingMixin):
    """
    Post spider template.
    Attributes here are re-used extensively by post pipelines,
    ie., PostMixin subclasses.

    #TODO: improved topic modeling through (LDA, LSTM?).
        `post.keywords` does mere word frequency analysis.
    """

    # PostCrawler template & defaults
    # nota: will get overridden by `init()` kwargs
    # -----------------------------------------------------------------------------------------------
    country_code = None         # Alpha‑2 ISO 3166 country code
    language = None             # language of post

    # below date specs will get parsed into `filter_dates`,
    # a list of days to consider for crawling.
    days_from: str = None            # crawl_all posts published at least since `days_from`.
    days_to: str = None              # crawl_all posts published at most  `days_to`;  today if None.
    days: [str] = []                   # single dates

    # scrap posts only from pages links extracted by below xpath strings.
    # eg. 'default', 'featured': are XPath lookup strings for resp. the regular, and featured posts types.
    # https://devhints.io/xpath
    post_images: str = None
    post_texts: Mapping[str, str] = {
        FEATURED_POST: None,
        DEFAULT_POST: None,
    }

    # -----------------------------------------------------------------------------------------------

    def parse_post(self, response, type: str) -> Post:

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

        # like Post(), but with the defaults presets
        post = mk_post(
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
            is_draft=not self.settings["POSTS"]['auto_publish']
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
        if self.post_images:
            try:
                images = response.xpath(self.post_images).extract()
            except ValueError as e:
                self.log_info(f'{FAILED:<{PADDING}}{self.post_images}')
                self.log_debug(str(e))

        images = images or list(article3k.images)
        top_image = images[0] if images else article3k.top_image
        return images, top_image

    def get_post_context(self, *args, days={}, **kwargs):
        """ Builds/checks context for all posts to be scraped by this spider
        eg. language, days range to scrape, etc.
        """
        # FIXME: should pop cmdline opts from kwargs? eg. 'from', 'to'

        # required fields
        assert self.country_code, "`country_code` (ISO 3166-1) field required"
        assert self.post_texts, "`post_texts` field required"

        # clean user input, set defaults
        # cmdline args (kwargs) have priority over class attributes!
        _days = days.get('days', self.days)
        _days_from = days.get('days_from', self.days_from)
        _days_to = days.get('days_to', self.days_to)

        language = self.language or self.settings["POSTS"]['default_lang']

        # compute filter dates for crawling
        filter_dates = parse_dates(
            days_from=_days_from, days_to=_days_to, days=_days)

        return dict(filter_dates=filter_dates, language=language)


    @property
    def country(self):
        """ Country object from country code """
        return pycountry.countries.get(alpha_2=self.country_code)

    def get_authors(self, article: Article, response=None):
        """ Articles authors. """
        return list(map(lambda name: Author(
            name=name, profile_image="", role=""
        ), article.authors))


class BasePostCrawler(PostCrawlerMixin, CrawlSpider, metaclass=PostCrawlerMeta):
    """
    Generic (abstract) online news source-aware spider.
    `Sources are abstractions of online news vendors like huffpost or cnn`

    Enables associated pipelines (??) to also link posts
    with their corresponding news source (paper).
    """

    _paper = None

    def __init__(self, *args, **kwargs):

        self.__dict__.update(self.get_post_context(*args, **kwargs))
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


class PostCrawlerContextMeta(ItemMeta):
    """
    `PostCrawlerContext` Item class creator
    supports configurable fields (user-editable field names).
    """

    def __new__(mcs, class_name, bases, attrs):

        computed = (get_setting('DB_ID_FIELD'), )
        fields = (
            # Scrapy-defined attributes
            'name', 'start_urls', 'allowed_domains',
            # custom attributes
            'country_code', 'language', 'post_texts', 'post_images',
            'days_from', 'days_to', 'days'
        )
        new_attrs = {f: scrapy.Field() for f in (*computed, *fields)}
        new_attrs.update(attrs)
        return super().__new__(mcs, class_name, bases, new_attrs)


class PostCrawlerContext(scrapy.Item, metaclass=PostCrawlerContextMeta):
    """
    Context to initialise `BasePostCrawler` spider instances dynamically
    """
    pass


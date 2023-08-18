import abc
import datetime
from collections import deque
from typing import Mapping, Literal, Dict
from urllib.parse import urljoin

import dateparser
import nltk
import pycountry
import scrapy
from dateparser.search import search_dates
from htmldate import find_date
from newspaper.outputformatters import OutputFormatter
from scrapy.item import ItemMeta

from newsutils.logging import LoggingMixin, FAILED, OK, PADDING
from newsutils.logo import parse_logo
from daily_query.helpers import parse_dates, mk_datetime

from scrapy.spiders import Rule, CrawlSpider
from scrapy.linkextractors import LinkExtractor

from newspaper import Article, Config, build

from .items import Author, Paper
from newsutils.conf.post_item import Post, mk_post
from newsutils.conf import TYPE, get_setting, USER_AGENT

nltk.download('punkt')


__all__ = [
    "PostRuleSets",
    "PostCrawlerMeta", "PostCrawlerMixin", "BasePostCrawler", "PostCrawlerContext",
    "DEFAULT_POST", "FEATURED_POST"
]


config = Config()
config.browser_user_agent = USER_AGENT
config.request_timeout = 10


# default post types
DEFAULT_POST = "default"
FEATURED_POST = "featured"


PostRuleSets = Mapping[Literal["link", "text", "images", "published"], str]


class PostCrawlerMeta(abc.ABCMeta):
    """
    Sets crawl rules dynamically based on the `.rule_sets` classproperty.
    Introduces rule sets as xpaths locators for an article's text, image, publication date.
    https://stackoverflow.com/a/25352434
    https://realpython.com/python-metaclasses/
    https://www.geeksforgeeks.org/__new__-in-python/
    """

    def __new__(cls, *args, **kwargs):
        crawler = super().__new__(cls, *args, **kwargs)
        cls.validate_rule_sets(cls, crawler)

        # dynamic crawl_all rules:
        # hooking `.from_crawler()`, so that crawl's Spider._set_crawler() gets a
        # chance to initialise `.settings` and connect the `spider_closed` signal
        # https://stackoverflow.com/a/27514672, https://stackoverflow.com/a/25352434
        crawler.rules = [
            Rule(
                LinkExtractor(restrict_xpaths=[xpath]),
                cb_kwargs={TYPE: post_type, 'rules': rules}, callback='parse_post',
                follow=False,
            )
            # rules -> PostRuleSets of both text and images
            for post_type, rules in crawler.rule_sets.items()
            for (mimetype, xpath) in (rules or {}).items() if mimetype == 'link'
        ]
        return crawler

    def validate_rule_sets(cls, crawler):

        # TODO: yaml validation (TODO: first, store spider context as yaml field)
        assert crawler.rule_sets and filter(None, crawler.rule_sets.values()), \
            "`rule_sets` must be a mapping of post_type (eg. 'default', 'featured'), " \
            "with values resp. PostRuleSets"


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

    # Define extraction rules as xpath strings, that yield links to extract text and images from.
    # By default, we define below two extraction rules called 'default', 'featured'
    # suitable for common use-cases, to lookup resp. regular, and featured posts.
    # https://devhints.io/xpath
    rule_sets: Mapping[str, PostRuleSets] = {
        FEATURED_POST: None,
        DEFAULT_POST: None,
    }

    def parse_post(self, response, type, rules) -> Post:
        """
        :param str type: post type
        :param PostRuleSets rules: set of xpath strings pointers
            for extracting text and images urls, as well as the publication date from an article.
        """

        a = Article(response.url, config=config)
        a.download()
        a.parse()

        # custom text extraction from article
        self.set_post_text(a, rules=dict(
            text=rules.get('text'),
            remove_text=rules.get('remove_text'),
        ))

        # required to parse summary, keywords, etc.
        # based off the article's .text, hence called after .parse()
        # FIXME: set NLP language to that of post based on the scraper's country, language props.
        a.nlp()

        short_link = a.url.replace(a.source_url, '')

        # quit processing posts that'll eventually get dropped by pipelines
        # cf. `newsutils.pipelines.FilterDate`
        publish_time = self.parse_post_time(response, a, xpath=rules.get('published'), coerce=True)
        if publish_time.date() not in self.filter_dates:
            self.log_info(f'{OK:<{PADDING}}' 
                          f'skipping expired {type} article {short_link}: '
                          f'published {publish_time}, valid: {", ".join(map(str, self.filter_dates))}')
            return None

        images, top_image = self.parse_post_images(response, a, rules['images'])
        self.log_info(f"{OK if len(images) else FAILED:<{PADDING}}"
                      f"parsing (%d/%d) image(s) for post {short_link}"
                      % (len(images), len(list(a.images))))

        # like Post(), but with the defaults presets
        post = mk_post(

            # post data
            country=self.country.alpha_2,
            link=a.url,
            short_link=short_link,
            title=a.title,
            text=a.text,
            excerpt=a.summary,
            publish_time=str(publish_time),
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
            is_draft=not self.settings["POSTS"]['auto_publish'],
        )

        self.log_info(f'{OK:<{PADDING}}' 
                      f'parsing {type} post {post["short_link"]}')
        return post

    def set_post_text(self, a, rules) -> None:
        """
        Customized extraction of article text
        Works by setting the node (`top_node`) whom to extract text from,
        then dropping nodes containing undesirable text (`remove_text`) from it.

        :param Article a: article
        :param PostRuleSets rules: xpaths
        """

        # top_node is the basis of text extraction
        # cf. newspaper.Article.parse()
        if not a.top_node:
            return a.text

        texts = []
        r = rules.get('text')
        for root_xpath in (r if isinstance(r, (list, tuple)) else [r]):

            try:
                # node to extract text from (take first matching only)
                top_node = next(iter(a.top_node.xpath(root_xpath)), a.top_node) \
                    if root_xpath else a.top_node

                # drop children nodes containing undesirable text
                # Nota: call .remove() on parent element only!
                if r := rules.get('remove_text'):
                    for xpath in (r if isinstance(r, (list, tuple)) else [r]):
                        deque(map(lambda e: e.getparent().remove(e),
                                  top_node.xpath(xpath)), maxlen=0)

                # actual text extraction
                output_formatter = OutputFormatter(a.config)
                text, _ = output_formatter.get_formatted(top_node)
                texts.append(text or top_node.text)

            except Exception as e:
                self.log_info(f'{FAILED:<{PADDING}}{p}')
                self.log_debug(str(e))

        a.set_text("\n\n".join(texts))

    def parse_post_time(self, r, a: Article, xpath=None, coerce=False) -> str or datetime.datetime:
        """
        Guess the publication time from the article.
        Tries few heuristics first, then attempt extraction from xpath if any,
        fails over to today, iff all of the above had fail.

        :param r: the response
        :param Article a: the article, as parsed by the newspaper3k library
        :param str xpath: xpath locator for the article's publication time
        :param bool coerce: whether to cast post publication time into datetime
        """

        # `extensive_search=True` (default) parses the article's copyright,
        # yields erroneous dates eg. '1998-01-01'
        post_time = str(a.publish_date) if a.publish_date \
            else find_date(a.html, extensive_search=False)
        if not post_time and xpath:
            try:
                post_time = l[0] if (l := r.xpath(xpath).extract()) else None
                post_time = next(iter(search_dates(post_time, languages=[
                    self.language.lower()]) or []), None)
                post_time = (post_time or [None])[1]

            except ValueError as e:
                if not "XPath error" in str(e):
                    raise
                err_msg = \
                    (f"{FAILED:<{PADDING}} post time extraction failed, "
                     f"assuming `today: {xpath}`")
                self.log_info(err_msg)
                self.log_debug(f"{str(e)}: {xpath}")

        # `mk_datetime` returns now time if post_time was None
        if coerce:
            post_time = mk_datetime(post_time)
        return post_time

    def parse_post_images(self, r, a, xpath: str or list or tuple):
        """
        Improved images url parsing vs `newspaper` module
        Rationale: not all images intermeddled with a post text are relevant to that post
        (eg. interstitial ads).

        :param HtmlResponse r: the response
        :param Article a: the article, as parsed by the newspaper3k library
        :param str or [str] xpath: xpath locator for the article's publication time

        TODO: move to pipeline?  burden of image parsing if the post
            might be later deleted by the `DropNoqaImages`

        TODO: also capture url from anchor tag of images (ad detection purposes)
        TODO: perform ad detection here or inside pipeline
        """
        images = set()
        if xpath:
            for p in (xpath if isinstance(xpath, (list, tuple)) else [xpath]):
                try:
                    if (r.xpath(p).get() or '').startswith('<img'):
                        p = f"{p}/@src"
                    images.update(map(lambda x: urljoin(a.url, x), r.xpath(p).extract()))
                except ValueError as e:
                    self.log_info(f'{FAILED:<{PADDING}}{p}')
                    self.log_debug(str(e))

        images = list(images or a.images)
        top_image = images[0] if images else urljoin(a.url, a.top_image)
        return images, top_image

    def get_post_context(self, *args, days={}, **kwargs):
        """ Builds/checks context for all posts to be scraped by this spider
        eg. language, days range to scrape, etc.
        """
        # FIXME: should pop cmdline opts from kwargs? eg. 'from', 'to'

        # required fields
        assert self.country_code, "`country_code` (ISO 3166-1) field required"
        assert self.rule_sets, "`rule_sets` field required"

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

        for name in ['logo', self.source.brand]:
            imgs = parse_logo(response, name)["img_url_list"]
            if imgs:
                break

        logo, status = (imgs[0], OK) if imgs else (None, FAILED)
        self.log_debug(f"{status:<{PADDING}} parsing logo for brand '{self.source.brand}' "
                       f"(out of {len(imgs)} images): {str(logo)}")
        return logo

    def parse_post(self, response, type, rules) -> Post:
        """ Override. Links newspaper with post. """

        post = super().parse_post(response, type, rules)
        if post:
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
            # meta-fields
            'version',
            # Scrapy-defined attributes
            'name', 'start_urls', 'allowed_domains',
            # custom attributes
            'country_code', 'language', 'rule_sets',
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


# scrapy-newsutils

This Python library makes scraping online articles a breeze. What you can do:

* Download articles from any format into a standardized `Post` structure,
* Gather posts by affinity, generates authentic titles and summaries from downloaded articles, etc.
* Generate summary, caption, category for scraped content using NLP.
* Generate meta summaries from posts grouped by affinty (concept of sibling posts) using NLP.
* Remove ads and undesirable content using NLP.
* Publish summarized posts to Telegram, Facebook and Twitter.
* Initialise scrapers dynamically from database settings.
* Create schedules to start crawl jobs.
  
It Provides following two major components for news fetching:
  - `newsutils.crawl` leverages Scrapy to crawl news.
  - `newsutils.ezines` downloads news by performing http requests to news API endpoints.


## Misc. Features

* Skips duplicate articles while crawling.
* Customizable names for article data fields.
* Customizable strategies for text extraction `summary_as_text`
* Comes with default settings overridable from the `.env` or `settings.py`
* Supply fuly-functional base classes for building customized commands, spiders and configuration that consume NLP pipelines.
* Mechanism to quit running a command if another instance is already running.

## Usage 

* Setup python env 
```shell
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

* Define a posts spider manually.
Traditional way, by defining the spider subclass in a module inside `settings.SPIDER_MODULES`

```shell
cat <<EOF > spiders/gn_guineematin.py
from newsutils.crawl.spiders import BasePostCrawler

class GnGuineeMatin(BasePostCrawler):
    """
    Scraps news posts at 'https://guineematin.com'
    """

    # by `scrapy.spider.Spider`
    name = 'gn-guineematin'
    allowed_domains = ['guineematin.com']
    start_urls = ['https://guineematin.com/']

    # by `newsutils.scrapy.base.spiders.NewsSpider`
    country_code = 'GN'
    language = 'fr'
    post_images = "//figure/img/@src"
    post_texts = {
        "featured": '//*[(@id = "tdi_82")]//a | //*[(@id = "tdi_84")]//a',
        "default": '//*[contains(concat( " ", @class, " " ), concat( " ", "td-animation-stack", " " ))]//a',
    }
    # days_from = '2022-04-19'
    # days_to = '2022-04-25'
    # days = ['2022-04-12', '2022-04-09']
EOF
```

* Define a posts spider dynamically. 
Initialisation context is read from the database as part of the project.
cf. `settings.CRAWL_DB_URI`. Eg., run following and import generated `spiders.json` to MongoDB
  
    ```shell
    cat <<EOF >  spiders.json
    [
      {
        "name": "gn-guineematin ",
        "allowed_domains": ["guineematin.com"],
        "start_urls": ["https://guineematin.com/"],
        "country_code": "GN",
        "language": "fr",
        "post_images": "//figure/img/@src",
        "post_texts": {
            "featured": "//*[(@id = \"tdi_82\")]//a | //*[(@id = \"tdi_84\")]//a",
            "default": "//*[contains(concat( \" \", @class, \" \" ), concat( \" \", \"td-animation-stack\", \" \" ))]//a"
        }
      }
    ]
    ```

* Run the spider (chdir to project directory)

    ```shell
    # redirects output to json file
    scrapy crawl gn-guineematin -O gn-guineematin.json
    ```


### Optimisations 

* Supports `conda` envs suited for machine learning.

* `scrapy nlp` command downloading 2G+ models data !
It is recommended to mount the NLP data directories as a volume when using Docker.
Cf. example multistage `Dockerfile` in the `leeram-news/newsbot` project.

* Throttled e-zines API requests rate at thesportsdb.com
  Configurable through env vars.

* [TODO] Skip NLP inference, ie. quit generating a metapost if exists a metapost with the same version in the db
  ie. iff same siblings detected.

* [TODO] Create a single source of through for settings: settings.py, envs loaded by the run.py script
  eg. SIMILARITY_RELATED_THRESHOLD, etc.

* [TODO] [NER as middleware](https://github.com/vu3jej/scrapy-corenlp) -> new post field

* [TODO] [Scrapy DeltaFetch](https://github.com/ScrapeOps/python-scrapy-playbook/tree/master/2_Scrapy_Guides) ensures that your scrapers only ever crawl the content once

* [TODO] Bulk (batch) Insert to Database
  append to some bucket during `process_item()`. to only flush to db during pieline's `close_spider()`
  https://jerrynsh.com/5-useful-tips-while-working-with-python-scrapy/

* [TODO] Move code for fetching post's `.images`, `.top_image` to Pipeline/Middleware
  Currently parses/downloads images event for dup posts uti !
    https://github.com/scrapy/scrapy/issues/2436
    https://doc.scrapy.org/en/latest/topics/spider-middleware.html#scrapy.spidermiddlewares.SpiderMiddleware.process_spider_output


### Feature request

* Bypass scraper blocking

  Refs: [1](https://scrapfly.io/blog/web-scraping-with-scrapy/)
  Test the various plugins for proxy management, eg.:
    - (scrapy-rotating-proxies)[https://github.com/TeamHG-Memex/scrapy-rotating-proxies],
    - (scrapy-fake-useragent)[https://github.com/alecxe/scrapy-fake-useragent], for randomizing user agent headers.

* Browser emulation and scraping dynamic pages (JS) using:
    - scrapy-selenium (+GCP): 
      [1](https://youtu.be/2LwrUu9yTAo),
      [2](https://www.roelpeters.be/how-to-deploy-a-scraping-script-and-selenium-in-google-cloud-run/)
    - [scrapy-playwright](https://pypi.org/project/scrapy-playwright/)
    - JS support via (Splash)[https://splash.readthedocs.io/en/stable/faq.html]  \
      Won't do: seem to require running in docker container??
      
* Migrate to Distributed scraping, eg. [Frontera](https://github.com/scrapinghub/frontera) 





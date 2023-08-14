

## Features

* Provides following two components for news fetching:
  - `newsutils.crawl` leverages Scrapy to crawl news.
  - `newsutils.ezines` downloads news by performing http requests to news API endpoints.
* Initialises scrapers dynamically from database settings.
* NLP summarization tasks: likely summary, caption, category of scraped posts
* Publish summarized posts to social networks.


### Optimisations 

* Supports `conda` envs suited for machine learning.

* `scrapy nlp` command downloading 2G+ models data !
It is recommended to mount the NLP data directories as a volume when using Docker.
Cf. example multistage `Dockerfile` in the `leeram-news/newsbot` project.

* Throttled e-zines API requests rate at thesportsdb.com
  Configurable through env vars.

* [OK] Don't process image for obsolete post (outside days_from/days_to bounds)

* [TODO] Skip NLP inference, ie. quit generating a metapost if exists a metapost with the same version in the db
  ie. iff same siblings detected.

* [TODO] Create a single source of through for settings: settings.py, envs loaded by the run.py script
  eg. SIMILARITY_RELATED_THRESHOLD, etc.

* [TODO] [NER as middleware](https://github.com/vu3jej/scrapy-corenlp) -> new post field

* [TODO] Don't dupe-download ! Following options:
  [Scrapy DeltaFetch](https://github.com/ScrapeOps/python-scrapy-playbook/tree/master/2_Scrapy_Guides) ensures that your scrapers only ever crawl the content once
  [Python Memoization](https://joblib.readthedocs.io/en/stable/)

* [TODO] Bulk (batch) Insert to Database
  append to some bucket during `process_item()`. to only flush to db during pipeline's `close_spider()`
  https://jerrynsh.com/5-useful-tips-while-working-with-python-scrapy/

* [TODO] Move code for fetching post's `.images`, `.top_image` to Pipeline/Middleware
  Currently parses/downloads images event for dup posts uti !
    https://github.com/scrapy/scrapy/issues/2436
    https://doc.scrapy.org/en/latest/topics/spider-middleware.html#scrapy.spidermiddlewares.SpiderMiddleware.process_spider_output


### Feature request

* One XPath selector per `PostCrawlerMixin.post_type` instead of unique selector for all types.
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



## Dev 

### Requirements

* running MongoDb instance (required by `newsbot`, `newsapi`)

    ```shell
    docker run -d -p 27017:27017 --name mongodb \
      -v pgdata:/var/lib/postgresql/data \
      mongo:latest
    ```
  
### Demo

* Setup python env 
```shell
python -m venv venv && source venv/bin/activate
pip install -r dev-requirements.txt
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
    rule_sets = {
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
cf. `settings.DB_URI`. Eg., run following and import generated `spiders.json` to MongoDB \
**Nota**: Set the `.version` field to integer value `0` to disable a spider,
otherwise loads latest version of any spider. 

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
        "rule_sets": {
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

## FIXES

1. ezine APIs: custom throttling setting in `newsutils/ezines/thesportsdb.py`
2. spiderloader: validate spider context loaded from db['_spiders'] (save first as yaml field)
3. spider stats -> db['_spiders']


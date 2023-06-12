

## Features

* conda-ready since contains 
* Optimisations [TODO]:
  - Skip NLP inference, ie. quit generating a metapost if exists a metapost with the same version in the db
  - Utilise only half of the symmetric TF-IDF matrix
  - Use TF-IDF from Spacy or SkLearn 
  - Resume vectorization of corpus where last task left off.
    This implies saving vectorization result to disk, and merging with docs newly added to the db. 

## Python env setup 

```shell
python -m pip install pip-tools
pip-compile --output-file=demo/requirements.txt
```

## Env vars setup

```shell
# posts
METAPOST_BASEURL=http://localhost:3100/posts

# networks
FACEBOOK_PAGE_ID= \
FACEBOOK_PAGE_ACCESS_TOKEN=
```

```shell
export \
    PROJECT_SETTINGS_MODULE=crawler.settings \
    POSTS=metapost_baseurl=${METAPOST_BASEURL} \
    PUBLISH=facebook_page_id=${FACEBOOK_PAGE_ID},facebook_page_access_token=${FACEBOOK_PAGE_ACCESS_TOKEN}
```

## Run commands

```shell
scrapy publish facebook,twitter -p -D from=2023-03-21 -M metrics=follows,likes,visits -M dimensions=status,feeds -k publish
```


## TODO

### Optimisation

* 


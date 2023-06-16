

## Features

* conda-ready since contains 
* Optimisations [TODO]:
  - Skip NLP inference, ie. quit generating a metapost if exists a metapost with the same version in the db
  - Utilise only half of the symmetric TF-IDF matrix
  - Use TF-IDF from Spacy or SkLearn 
  - Resume vectorization of corpus where last task left off.
    This implies saving vectorization result to disk, and merging with docs newly added to the db. 
  - Cython ??
  - 
## Setup the demo 

* Setup python env 
```shell
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

* Set envvars
```shell
export \
    PROJECT_SETTINGS_MODULE=crawler.settings \
    METAPOST_BASEURL = 'http://localhost:3000/posts/'
```

## Run commands

```shell
scrapy publish facebook,twitter -p -D from=2023-03-21 -M metrics=follows,likes,visits -M dimensions=status,feeds -k publish
```




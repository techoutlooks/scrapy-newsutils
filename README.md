

## Features

* conda-ready since contains 
* Optimisations :
  - [TODO] Skip NLP inference, ie. quit generating a metapost if exists a metapost with the same version in the db
    ie. iff same siblings detected.
  - 
* [TODO] Experiment with definition with MongoDB replica set
  https://www.ibm.com/docs/en/mas-cd/continuous-delivery?topic=dependencies-installing-mongodb
  https://www.mongodb.com/docs/kubernetes-operator/stable/tutorial/deploy-standalone/
  https://humanitec.com/blog/deploy-with-kubectl-hands-on-with-kubernetes (postgresql StatefulSet)



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




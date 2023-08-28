
# Playground


APIs playground


Initialising the library
========================

* Start a python shell 

With minimal required settings:

```shell
cd ./src
ENV=development \
METAPOST_BASEURL=http://localhost:3100/posts \
SCRAPY_SETTINGS_MODULE=crawler.settings \
python
```

* Initialize the newsutils lib

```python
from newsutils.conf import configure
configure()
```


Project settings
================

* Getting project settings


```python

# way 1
from scrapy.utils.project import get_project_settings
s = get_project_settings()
s['POSTS']['metapost_link_factory']

# way 2
from newsutils.conf.globals import get_setting
get_setting('POSTS.metapost_link_factory')
```


NLP
===


* Bootstraping 

```python
from daily_query.mongo import MongoDaily
from newsutils.nlp import DayNlp

# MongoDB connection string or without auth
# db_uri = 'mongodb://localhost:27017/scraped_news_db' 
db_uri = 'mongodb://techu:techu0910!@localhost:27017/scraped_news_db?authSource=admin'

# set up to lookup for given post
# this will download HuggingFace pretrained models locally (Cf. the DATA_DIR and CACHE_DIR envs)
daily = MongoDaily(db_uri)
collections, counts = daily.get_collections(days=['2023-08-18'])
nlp = DayNlp(collections[0])
```

* Lookup posts by their id (or ObjectId)

```python

lookup = '64dfea359d5812c058e31939'

# using bare database _id string
>>> nlp[lookup]['title']
'Ousmane Sonko en réanimation !'

>>> nlp[lookup]['caption']
'Sénégal : le président Ousmane Sonko en réanimation'

>>> nlp[lookup]['summary']
'Ousmane Sonko est admis en réanimation. «Nous portons à la connaissance de l’opinion nationale et internationale que Le leader des patriotes, est ce jeudi 17 août 2023 à son 19ème jour de la grève de la faim.'

# using Mongo ObjectId
from bson import ObjectId
>>> nlp[ObjectId(lookup)]['title']	
'Ousmane Sonko en réanimation !'
```


* Get various nlp levels

```python

# post similarity
>>> nlp.similarity
OrderedDict([('siblings', {'threshold': 0.21, 'top_n': 5}), ('related', {'threshold': 0.11, 'top_n': 5})])

# likelihood of post content being crap 
>>> nlp.crap_similarity_threshold
0.25

# don't generate metapost if compound text (several posts) 
# is shorter than 51
>>> nlp.summary_minimum_length
51

# BRISQUE (Blind Reference-less Image Spatial Quality Evaluator)
# level not to exceed for acceptable picture quality
>>> nlp.image_brisque_max_score
50

```

* Generate a text corpus from database posts

```python
corpus = filter(None, [nlp.get_decision("get_post_text")(p) for p in nlp.posts])
```

* Get posts similar to lookup

```python

post = nlp[lookup]
post_i = nlp.posts.index(post)	# post_i = 26

# using defaults {'threshold': 0.21, 'top_n': 5}
# yields similar = [(8, 0.23964807823108797)]
# ie., we get 23% similarity with the 8th post in the document corpus
>>> similar = nlp.vectorizer.similar_to(post_i, **nlp.similarity['siblings'])
>>> nlp[8]['title']			
"Principal : Des nouvelles sur l'état de santé de Ousmane Sonko"
>>> nlp[8]['caption']
'Ousmane Sonko hospitalisé : les militants de Pastef inquiets'


# with >= 15% similarity (likely production)
# yields [(8, 0.23964807823108797), (19, 0.2056203170676129), (42, 0.16086498271540325)]
>>> nlp.vectorizer.similar_to(post_i, threshold=0.15, top_n=5)
[(8, 0.23964807823108797), (19, 0.2056203170676129), (42, 0.16086498271540325)]
>>> nlp[8]['caption']
'Ousmane Sonko hospitalisé : les militants de Pastef inquiets'
>>> nlp[19]['caption']
"Sénégal : l'administration pénitentiaire brise le silence sur la grève de la faim"
>>> nlp[42]['caption']
"Grève de faim d'Ousmane Sonko: sa famille se prononce"


nlp[8]['title']			# "Principal : Des nouvelles sur l'état de santé de Ousmane Sonko"
nlp[19]['title']		# "État de Sonko, Bara Ndiaye et Hannibal Djim : L'administration pénitentiaire brise le silence !"
nlp[42]['title']		# "Grève de faim d'Ousmane Sonko: sa famille se prononce"


# with >= 15% similarity 
# but starting with the 42th post
>>> nlp.vectorizer.similar_to(42, threshold=0.15, top_n=5)
[(26, 0.16086498271540325), (4, 0.15686328336416733), (8, 0.15481557619414305)]

>>> nlp[4]['title']		# this is lookup2
'La demande poignante des épouses de Sonko à Macky, son épouse et au peuple'
>>> nlp[26]['title']
'Ousmane Sonko en réanimation !'
>>> nlp[8]['title']
"Principal : Des nouvelles sur l'état de santé de Ousmane Sonko"


```


# yields None
next(filter(lambda p: str(p[nlp.db_id_field]) == str(lookup), nlp.posts), None)


# yields None
_posts = list(nlp.find_max('version', nlp.item_id_field, {}))
next(filter(lambda p: str(p[nlp.db_id_field]) == lookup, _posts), None)


# yields a post ... OK
next(filter(lambda p: str(p[nlp.db_id_field]) == lookup, nlp.find()), None)


# using aggregation query
# yields None

def find_max(field, groupby, match={}):
    """ Select documents with max value of a field """
    max_ver = [
        {'$match': match}, 
        # {'$sort': {groupby: 1, field: -1}},
        {'$sort': {'short_link': 1, 'version': -1}},

        {'$group': {'_id': f"${groupby}", 'doc_with_max_ver': {'$first': "$$ROOT"}}},
        {'$replaceWith': "$doc_with_max_ver"}
    ]
    return nlp.aggregate(max_ver)

_posts = list(find_max(field='version', groupby=nlp.item_id_field))
next(filter(lambda p: str(p[nlp.db_id_field]) == lookup, _posts), None)




_posts = nlp.aggregate([
	{'$match': {'short_link': '/irevue.php'}},
	{'$sort': {"short_link": 1, "version": -1}},
	{'$group': {'_id': "$short_link", 'doc_with_max_ver': {'$first': "$$ROOT"}}},
	{'$replaceWith': "$doc_with_max_ver"}])
next(filter(lambda p: str(p[nlp.db_id_field]) == lookup, _posts), None)



[
  {
    $sort: {
      short_link: 1,
      version: -1,
    },
  },
  {
    $group: {
      _id: "$short_link",
      doc_with_max_ver: {
        $first: "$$ROOT",
      },
    },
  },
  {
    $replaceWith: "$doc_with_max_ver",
  },
]


/**
 * replacementDocument: A document or string.
 */
{
  newWith: replacementDocument
}



        for ctx in db_col.find_max('version', groupby='name', match={'version': {'$nin': [0]}}):



from newspaper import Article

url = 'https://www.igfm.sn/appel-telephonique-macky-khalifa-et-sonko-les-revelations-de-barth'
a = Article(r.url)
a.download()



xpath = '//p[contains(concat(" ",normalize-space(@class)," ")," label ")]'
elts = a.top_node.xpath(xpath)
e = elts[0]


 a.top_node.remove(e)





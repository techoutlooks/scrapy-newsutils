from collections import OrderedDict
from typing import Generator, Iterable

from bson import ObjectId
from itemadapter import ItemAdapter

from daily_query.helpers import mk_date
from daily_query.mongo import Collection

# from .items import *
# from .spiders import *
# from .pipelines import *
# from .posts import *
from .settings import *

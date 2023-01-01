from collections import OrderedDict
from typing import Iterable

from bson import ObjectId
from itemadapter import ItemAdapter

from daily_query.helpers import mk_date
from daily_query.mongo import Collection

from ..helpers import compose, add_fullstop
from ..conf.mixins import BaseConfigMixin
from ..fields import TITLE, EXCERPT, TEXT, SHORT_LINK, TYPE, UNKNOWN
from .items import Post


__all__ = ['Day', 'PostConfigMixin']


class PostConfigMixin(BaseConfigMixin):
    """ Mixin. Exposes utility class attribues. """

    # FIXME: fields polluting the namespace,
    #    use DataClassCard in AppSettings? or set attrs here from snake_cased settings?
    settings = BaseConfigMixin.settings

    # ITEM
    # `item_id_field`: Identifies crawled items uniquely. NOT the database id.
    item_id_field = settings['POSTS']['ITEM_ID_FIELD']

    # NLP FIELDS
    caption_field = settings['POSTS']['CAPTION_FIELD']
    category_field = settings['POSTS']["CATEGORY_FIELD"]
    summary_field = settings['POSTS']['SUMMARY_FIELD']
    siblings_field = settings['POSTS']["SIBLINGS_FIELD"]
    related_field = settings['POSTS']["RELATED_FIELD"]

    # MISC FIELDS
    computed_fields = settings['POSTS']['COMPUTED_FIELDS']
    edits_excluded_fields = settings['POSTS']["EDITS_EXCLUDED_FIELDS"]
    edits_new_version_fields = settings['POSTS']["EDITS_NEW_VERSION_FIELDS"]
    image_min_size = settings['POSTS']['IMAGE_MIN_SIZE']
    image_brisque_max_score = settings['POSTS']['IMAGE_BRISQUE_MAX_SCORE']
    image_brisque_ignore_exception = settings['POSTS']['IMAGE_BRISQUE_IGNORE_EXCEPTION']

    def __init__(self, *args, **kwargs):
        """ Compute actual values for dynamic fields. """

        super().__init__(*args, **kwargs)

    @property
    def similarity(self):
        """ Settings for computing similarity scores amongst posts
        keys are also the proper kwargs of `TfidfVectorizer.similar_to()`
        """
        config = {
            self.siblings_field: {
                "threshold": self.settings['POSTS']['SIMILARITY_SIBLINGS_THRESHOLD'],
                "top_n": self.settings['POSTS']['SIMILARITY_MAX_DOCS']
            },
            self.related_field: {
                "threshold": self.settings['POSTS']['SIMILARITY_RELATED_THRESHOLD'],
                "top_n": self.settings['POSTS']['SIMILARITY_MAX_DOCS']
            },
        }

        config = OrderedDict(dict(sorted(
            config.items(), key=lambda it: it[1]["threshold"], reverse=True)))
        return config

    @classmethod
    @property
    def strategy(cls):
        """
        Functions for decisions based on
        post's current value and configurable settings
        """

        def filter_metapost(post: Post):
            """ Should filter out the current post if it is a metapost ? """
            if post.is_meta and \
                    not cls.settings['POSTS']['NLP_USES_META']:
                return
            return post

        def get_post_text(post: Post, meta=False):
            """
            Get all meaningful text from post, post's title and body alike.

            :param bool meta: a metapost being generated,
                    but `post` is unaware (post.is_meta not set yet)
            :param Post post: the post item
            """

            # default
            uses_nlp = not post.is_meta and cls.settings['POSTS']['SUMMARY_USES_NLP']
            title, text = (TITLE, EXCERPT if uses_nlp else TEXT)

            # metapost only
            if post.is_meta or meta:
                uses_nlp = cls.settings['POSTS']['META_USES_NLP']
                title, text = (cls.caption_field if uses_nlp else TITLE,
                               cls.summary_field)

            return add_fullstop(post[title]) + " " + (post[text] or "")

        return {
            "filter_metapost": filter_metapost,
            "get_post_text": get_post_text,
        }


class Day(Collection, PostConfigMixin):
    """
    Database management facility for daily post items.
    Requires `PostConfig`.
    """

    posts = []

    def __init__(self, day):
        super().__init__(day, db_or_uri=self.db_uri)
        self.posts = list(self.get_posts())

    @property
    def date(self):  # str(self) -> the collection's name
        return mk_date(str(self))

    def get_posts(self) -> Iterable[Post]:
        """ Get posts based on strategy.
        Posts are loaded from db `as-is`, ie. not expanding related fields!
        :param Collection day: daily collection
        """
        pipe = compose(lambda p: self.strategy["filter_metapost"](p),
                       lambda p: Post(p))
        posts = map(pipe, self.find())
        posts = filter(None, posts)
        return posts

    def __getitem__(self, lookup):
        """
        Look up for post in loaded posts

        Usage: all below example return the found `Post` instance:
        >>> day[db_id]; day[post_index]; day[post]

        :param int or ObjectId or Post lookup: index, database id or post for post
            assumes key:str is str(ObjectId)
        :returns: found Post instance
        :rtype: Post
        """

        if isinstance(lookup, (str, ObjectId)):
            return next(filter(lambda p: str(p[self.db_id_field]) == str(lookup), self.posts), None)
        if isinstance(lookup, Post):
            return lookup if lookup in self.posts else None
        if isinstance(lookup, int):
            post = None
            try:
                post = self.posts[lookup]
            except KeyError:
                pass
            return post

    def __setitem__(self, lookup, value):
        """
        Update post identified by lookup inside **self.posts**.

        Usage:
        >>> day[db_id] = new_post; day[post_index] = new_post; day[post] = new_post

        :param int or ObjectId or Post lookup: index, database id or post for post
            assumes key:str is str(ObjectId)
        :param Post value: new post value to set
        """
        # 1) find index to update from lookup
        # 2) perform destructive update
        i = self.posts.index(self[lookup])
        self.posts[i] = value

    def save(self, post: Post):
        """ Updates, or creates a new post/metapost if `post` has no db id value.
        Uses `ItemAdapter` for proper fields checking vs. `Post` Item class.
        :returns (Post, modified_count) or (None, 0) if db was not hit.
        """

        _post, saved = None, 0
        log_msg = lambda detail: \
            f"saving post (type `{post.get(TYPE) or UNKNOWN}`) #" \
            f"{post.get(self.db_id_field, post[SHORT_LINK])} to db: " \
            f"{detail}"

        self.log_started(log_msg, '...')
        try:

            # save
            adapter = ItemAdapter(post)
            _id = ObjectId(adapter.item.get(self.db_id_field, None))
            adapter.update({self.db_id_field: _id})
            r = self.update_one(
                {'_id': {'$eq': _id}}, {"$set": adapter.asdict()}, upsert=True)
            _post, saved = adapter.item, r.modified_count

            # also, refect update in mem cache according to strategy,
            # iff the db update was successful. eg. don't update metaposts
            # if they were never loaded in the first place (metaposts filtered)
            if saved:
                if self.strategy["filter_metapost"](_post):
                    self[_id] = _post

            # log
            op = 'inserted' if r.upserted_id else 'updated'
            self.log_ok(log_msg, f"{op} ({r.modified_count}/{r.matched_count})")

        except Exception as exc:
            self.log_failed(log_msg, exc, '')

        return _post, saved

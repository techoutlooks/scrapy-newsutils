import hashlib
import time
from typing import Iterable
from urllib.parse import urlparse

from bson import ObjectId
from itemadapter import ItemAdapter

from daily_query.helpers import mk_date
from daily_query.mongo import Collection, Doc

from ..helpers import compose, dotdict
from ..conf.post_item import Post
from ..conf.mixins import PostStrategyMixin
from newsutils.conf import TaskTypes, \
    LINK, SHORT_LINK, TYPE, UNKNOWN, VERSION, LINK_HASH

__all__ = ['Day']


class Day(PostStrategyMixin, Collection):
    """
    Database management facility for daily post items.
    Is aware of the post type eg. `metapost`, `featured`, `default`
    """

    posts: [Post] = []
    task_type = None

    def __init__(self, day, task_type=None, match={}):
        """
        :param day: the day
        :param TaskTypes task_type: type of the cmd task instantiating this class.
            Helps define strategies eg. which post types to load. cf. PostStrategyMixin.
        :param dict match: posts match filter:
            passed on as-is to db engine's `.find(match=match)` method
        """

        # sets `self.day` as collection
        super().__init__(day, db_or_uri=self.db_uri)
        self.task_type = task_type
        self.posts = list(self.get_posts(**match))

    @property
    def date(self):  # str(self) -> the collection's name
        return mk_date(str(self))

    def get_posts(self, **match) -> Iterable[Post]:
        """ Get posts based on strategy.
        Posts are loaded from db `as-is`, ie. not expanding related fields!
        Loads only last version of documents.
        """

        # execute filters in reverse-order (last runs first)
        # `filter_metapost()` - load only desired post types
        # `get_post_text()`   - load only post with desired total texts length
        pipe = compose(
            lambda p: self.get_decision("filter_metapost")(p, self.task_type),
            lambda p: p if self.get_decision("get_post_text")(p) else None,
            lambda p: Post(p)
        )

        posts = map(pipe, self.find_max(VERSION, self.item_id_field, match))
        posts = filter(None, posts)
        return posts

    def __len__(self):
        return len(self.posts)

    def __getitem__(self, lookup):
        """
        Look up for post in loaded posts (`self.posts`)

        Usage: all below example return the found `Post` instance:
        >>> day[db_id]; day[post_index]; day[post]

        :param int|ObjectId|Post lookup: post to lookup, or its id or index relative to `self.posts`
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

    def __setitem__(self, loc, post):
        """
        Updates (destructive) post identified by `lookup` inside `self.posts`.

        :param int|ObjectId|Post loc: location in `self.posts` to override
        :param Post post: new post value to set

        Usage:
        >>> day[db_id] = new_post; day[post_index] = new_post; day[post] = new_post
        """
        existed = self[loc]
        if existed:
            self.posts[self.posts.index(existed)] = post
        else:
            self += post

    def __add__(self, other):
        self.posts += [other]

    def save(self, post: Post, id_field_or_match=None, only=None):
        """ Upsert post matched by given `id`, `match` or `only` fields.
        Uses `ItemAdapter` for proper fields checking vs. `Post` Item class.

        :param post: post to update or create
        :param str|dict id_field_or_match:
            custom `_id` field name to lookup by. Defaults to the configured setting, eg. `_id`,
            or lookup dictionary
        :param Iterable[str] only: only alter the db iff `only` fields on post vs db are identical.
        :rtype: Post
        """

        def set_metapost_link(d: Doc):
            if Post(d).is_meta:

                d[LINK] = self.get_decision('get_metapost_link')(d)
                short_link = urlparse(d[LINK]).path
                d[SHORT_LINK] = short_link

                d[LINK_HASH] = '%s.%s' % ( # build link hash the same way as by newspaper3k lib
                    hashlib.md5(short_link.encode('utf-8', 'replace')).hexdigest(), time.time())

            return d

        db_post, created = None, False
        log_msg = lambda post=post, detail=None: \
            f"saving post (type `{post.get(TYPE) or UNKNOWN}`) #" \
            f"{post.get(self.db_id_field, post[SHORT_LINK])} to the db: " \
            f"{detail or '...'}"

        self.log_started(log_msg)
        try:
            adapter = ItemAdapter(post)
            match = {f: adapter.item.get(f) for f in (only or [])}
            if isinstance(id_field_or_match, dict):
                match.update(id_field_or_match)
            else:
                id_key = id_field_or_match or self.db_id_field
                id_value = adapter.item.get(id_field_or_match) if id_field_or_match \
                    else ObjectId(adapter.item.get(self.db_id_field, None))
                match.update({id_key: id_value})

            db_post, r = self.update_or_create(
                adapter.asdict(), transform=set_metapost_link, **match)

            # also, reflect update in mem cache according to strategy,
            # iff the db update was successful. eg., don't update metaposts
            # if they were never loaded in the first place (metaposts filtered)
            if db_post:
                db_post = Post(db_post)
                db_post_id = ObjectId(adapter.item[self.db_id_field])
                if self.get_decision("filter_metapost")(db_post, self.task_type):
                    self[db_post_id] = db_post

            # log
            op = 'inserted' if r.upserted_id else 'updated'
            self.log_ok(log_msg, post=db_post, detail=f"{op} ({r.modified_count}/{r.matched_count})")

        except Exception as exc:
            self.log_failed(log_msg, exc)

        return db_post

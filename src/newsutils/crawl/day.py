from typing import Iterable

from bson import ObjectId
from itemadapter import ItemAdapter

from daily_query.helpers import mk_date
from daily_query.mongo import Collection

from ..helpers import compose
from ..conf.post_item import Post
from ..conf.mixins import PostStrategyMixin
from newsutils.conf import TaskTypes, \
    SHORT_LINK, TYPE, UNKNOWN


__all__ = ['Day']


class Day(PostStrategyMixin, Collection):
    """
    Database management facility for daily post items.
    Requires `PostConfig`.
    """

    posts: [Post] = []

    def __init__(self, day, task_type=None, match={}):
        """
        :param day: the day
        :param TaskTypes task_type: type of the cmd task instantiating this class.
        :param dict match: posts match filter:
            passed on as-is to db engine's `.find(match=match)` method
        """
        super().__init__(day, db_or_uri=self.db_uri)
        self.task_type = task_type
        self.posts = list(self.get_posts(**match))

    @property
    def date(self):  # str(self) -> the collection's name
        return mk_date(str(self))

    def get_posts(self, **match) -> Iterable[Post]:
        """ Get posts based on strategy.
        Posts are loaded from db `as-is`, ie. not expanding related fields!
        """
        pipe = compose(
            lambda p: self.get_decision("filter_metapost")(p, self.task_type),
            lambda p: Post(p)
        )
        posts = map(pipe, self.find(match=match))
        posts = filter(None, posts)
        return posts

    def __len__(self):
        return len(self.posts)

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
                if self.get_decision("filter_metapost")(_post, self.task_type):
                    self[_id] = _post

            # log
            op = 'inserted' if r.upserted_id else 'updated'
            self.log_ok(log_msg, f"{op} ({r.modified_count}/{r.matched_count})")

        except Exception as exc:
            self.log_failed(log_msg, exc, '')

        return _post, saved

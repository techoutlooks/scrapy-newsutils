from bson import ObjectId

from daily_query.helpers import mk_datetime
from newsnlp import TextSummarizer, TitleSummarizer, Categorizer, TfidfVectorizer

from newsutils.scrapy.base.posts import PostConfigMixin, Day
from newsutils.helpers import wordcount, uniquedicts, dictdiff, add_fullstop
from .base.items import Post, mk_post, BOT, THIS_PAPER
from .base.settings import \
    TITLE, META_POST, SCORE, COUNTRY, TYPE, AUTHORS, PUBLISH_TIME, \
    MODIFIED_TIME, IMAGES, VIDEOS, TAGS, IS_DRAFT, IS_SCRAP, KEYWORDS, TOP_IMAGE, PAPER, UNKNOWN


CATEGORY_NOT_FOUND = 'N/A'


class DayNlp(Day, PostConfigMixin):
    """
    Helper to perform NLP on posts scraped a given day .

    FIXME: bugs if generating metaposts before computing similarity.
    """

    lang = "fr"
    strategy = PostConfigMixin.strategy

    posts: [Post] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # sets `self.day` as collection

        self.counts = dict(
            # resp. total posts processed/saved, words processed
            total=0, saved=0, words=0,
            # tfidf, (text, title, category)-summarization, meta-summarization
            similarity=0, summary=0, metapost=0
        )

        # nlp models
        corpus = [self.strategy["get_post_text"](p) for p in self.posts]
        self.vectorizer = TfidfVectorizer(lang="fr")(corpus)
        self.categorizer = Categorizer(lang="fr")
        self.text_summarizer = TextSummarizer(lang=self.lang)
        self.title_summarizer = TitleSummarizer(lang=self.lang)

        # stats for the day
        self.counts['similarity'] = self.vectorizer.num_docs
        self.counts['words'] = self.vectorizer.corpus_len
        self.counts['total'] = len(self.posts)

    def save_day(self, verb=None):

        def build_params(verb):
            params = {
                "similarity": {},
                "summary": {},
                META_POST: {},
            }

            # no verb, runs them all !
            return {verb: params.get(verb)} if verb \
                else params

        for verb, params in build_params(verb).items():
            for post in self.posts:
                save = getattr(self, "save_%s" % verb)
                _, status = save(post, **params)
                self.counts["saved"] += status

        self.log_ended(
            "saved ({saved}) fields in ({total}) docs, ({words}) words: "
            "generated (similarity/summary/metapost): {similarity}/{summary}/{metapost} posts. "
            f"published on {self}.", **self.counts)

        return self.counts

    def save_similarity(self, post: Post, overlap=False):
        """
        Compute similarity (`siblings`, `related` by default) scores
        of given post against the entire corpus., and persist it to the db.
        Docs are partitioned by similarity using respective threshold level.

        :param Post post: post doc to save similarity for
        :param bool overlap: include results from higher thresholds into lower ones?
        :returns: saved (post, count).
        :rtype: (Post, int)
        """

        # uses tfidf model to vectorise title+text of entire article corpus
        # `.similarity` holds params for the model's `similar_to` api.
        similar, saved = {}, 0 # 6290f008684d82f5922dfac7
        log_msg = lambda saved: \
            f"{'' if saved else 'NOT'} saving `{list(self.similarity)}` similarity " \
            f"({saved}) siblings, for doc #{post[self.db_id_field]} ..."

        self.log_started(log_msg, saved)
        for field, tfidf_params in self.similarity.items():

            # compute similar_docs and transform as db format, like so:
            # [{'_id': ObjectId('6283bcb2c176579f86acafb0'), 'score': 0.14859620818206487}, ...]
            similar_docs = self.get_similar(post, **tfidf_params)
            db_value = [{self.db_id_field: p[self.db_id_field], SCORE: score}
                        for p, score in similar_docs]

            # remove previous intersecting doc sets. generated sets have
            # cardinals inversely proportional to resp. similarity scores
            if not overlap:
                db_value = dictdiff(db_value, *similar.values())

            similar[field] = db_value

        try:
            if similar:
                post, saved = self.save(Post({**post, **similar}))
            self.log_ok(log_msg, saved=saved)

        except Exception as exc:
            self.log_failed(log_msg, exc, saved)

        self.counts["similarity"] = saved
        return post, saved

    def save_summary(self, post: Post):
        """
        Generate (destructive) abstractive summaries (title, text, categories)
        for given post, using computed values, and persist it to the database.

        :returns: saved (post, count).
        :rtype: (Post, int)
         """

        saved: int = 0
        text = self.strategy["get_post_text"](post)
        summary, caption, categories = self.get_summary(text)
        category = categories[0][0] if categories else CATEGORY_NOT_FOUND

        log_msg = lambda: \
            f"generating `summary` for doc #`{post[self.db_id_field]}`: " \
            f"summary: ({wordcount(summary)}/{wordcount(text)}) words, " \
            f"caption: ({wordcount(caption)}/{wordcount(post[TITLE])}) words, " \
            f"category: `{category}`."

        self.log_started(log_msg)
        try:
            post, saved = self.save(Post({
                **post,
                self.caption_field: caption,
                self.summary_field: summary,
                self.category_field: category}))
            self.log_ok(log_msg)

        except Exception as exc:
            self.log_failed(log_msg, exc)

        self.counts["summary"] = saved
        return post, saved

    def save_metapost(self, src: Post):
        """ Generate a meta post from given post's siblings,
         and save it to the database in the metapost's collection. """

        metapost, saved = None, 0
        log_msg = lambda status: \
            f"generating `{META_POST}` " \
            f"{'#' + str(metapost[self.db_id_field]) if status else ''} " \
            f"for post #{src[self.db_id_field]}: "

        self.log_started(log_msg, saved)
        metapost = self.mk_metapost(src)
        if metapost:
            try:
                metapost, saved = self.save(metapost)
                self.log_ok(log_msg, saved)
            except Exception as exc:
                self.log_failed(log_msg, exc, saved)

        self.counts[META_POST] = saved
        return metapost, saved

    def mk_metapost(self, src: Post):
        """ Generate a meta post by compiling all siblings
        of the given post, given the configured strategy.

        meta posts do NOT have following fields:
        TITLE, TEXT, EXCERPT, LINK, SHORT_LINK, LINK_HASH

        CAUTION: relies on `.save_summary()` to set values for fields `siblings`, `related`

        FIXME: summarizer currently only supports 1024 words max.
            find more powerful model? push model capacity?
            trim each text according to num_texts/1024 ratio.

        :returns: saved (metapost, count).
        :rtype: (Post, int)
        """

        # TODO: strategy to get metapost from other methods than TF-IDF,
        #   eg. kNN, kernels?
        metapost = None
        siblings = self.get_similar(src, from_field=self.siblings_field)
        siblings, _ = zip(*siblings) if siblings else ([], [])
        siblings_texts = [self.strategy["get_post_text"](p, meta=True) for p in siblings]
        _text = " ".join([add_fullstop(t) for t in siblings_texts])

        # exists _text, means there were non-empty siblings
        if _text:
            metapost = mk_post()

            # make a unique, yet predictable db_id from by summing sibling ids.
            # this guarantees db UPSERT-ion instead of invariably creating a new
            # metapost on every call. '0xc50e7a9799d7b9bb887365b8'
            hex_sum = hex(sum([int(f"0x{str(p[self.db_id_field])}", 16)
                               for p in siblings]))
            metapost[self.db_id_field] = ObjectId(hex_sum[2:2 + 24])  # strip `0x`, keep 24 characters

            # nlp fields
            summary, caption, categories = self.get_summary(_text)
            category = categories[0][0] if categories else CATEGORY_NOT_FOUND
            metapost[self.category_field] = category
            metapost[self.caption_field] = caption
            metapost[self.summary_field] = summary

            # siblings & related
            # from src post
            metapost[self.siblings_field] = src[self.siblings_field]
            metapost[self.related_field] = src[self.related_field]

            # immutable fields
            # `TOP_IMAGE` from most similar post (highest score)
            # `MODIFIED_TIME` is now
            metapost[TYPE] = "%s.%s" % (META_POST, src[TYPE])
            metapost[COUNTRY] = src[COUNTRY]
            metapost[PUBLISH_TIME] = str(mk_datetime(self))
            metapost[MODIFIED_TIME] = str(mk_datetime())
            metapost[TOP_IMAGE] = siblings[0][TOP_IMAGE]
            metapost[PAPER] = THIS_PAPER
            metapost[AUTHORS] = [BOT]

            # compile misc. data from siblings into metapost:
            # bool fields, str list fields, dict list fields
            for post in siblings:

                for f in IS_DRAFT, IS_SCRAP:  # bools
                    metapost[f] &= post[f]
                for f in IMAGES, VIDEOS, KEYWORDS, TAGS:  # strs
                    metapost[f] = list(set(metapost[f]).union(post[f]))
                for f in AUTHORS,:  # dicts
                    metapost[f] = uniquedicts(metapost[f], post[f])

        return metapost

    def get_similar(self, post, from_field=None, **kwargs):
        """
        Get (<post>, <similarity-score>) of posts similar to `post`,
        having similarity score of equal or above value `kwargs['threshold']`

        :param str from_field: re-run TF-IDF (the default)? or return post defaults.
        :param Post post: post whose similar docs are sought
        :param kwargs: optional params for `TfidfVectorizer`, (ie. `threshold`, `top_n`)
        :returns: [(Post, int)] : [( <post>, <score>), ...] of similar docs
        """

        if from_field:
            similar = self.expand_related(post, from_field)
            similar = list(map(lambda args: (args[0], args[1].get(SCORE)), similar))

        else:
            post_i: int = self.posts.index(post)
            similar = self.vectorizer.similar_to(post_i, **kwargs)
            similar = [(self.posts[j], score) for j, score in similar]

        log_msg = lambda post_score: \
            f"found ({len(similar)}) docs similar to " \
            f"#{post[self.db_id_field]} (@{post_score}) : " \
            f"{', '.join(['#{} (@{:.2f})'.format(p[self.db_id_field], score) for p, score in list(similar)])}"

        # threshold can't be recovered from db-saved post!
        score = UNKNOWN if from_field else kwargs.get('threshold')
        self.log_ok(log_msg, score)

        return similar

    def get_summary(self, text: str):

        summary = self.text_summarizer(text)
        caption = self.title_summarizer(text)
        categories = self.categorizer(text)
        return summary, caption, categories

    def expand_related(self, post: Post, field: str):
        """
        Expand the posts referred to by the `field` attribute of given post
        into plain Post objects

        :returns [(Post, dict)]: list of resp. the referred-to post and
                existing db value (value for `field`)
        """
        related: [Post] = []
        db_related = post.get(field)
        if db_related:
            for db_post in db_related:
                item_id = db_post.get(self.db_id_field)
                if item_id:                         # get the next post that matches
                    post = next(filter(              # id of the related item
                        lambda p: p[self.db_id_field] == item_id, self.posts), None)
                    if post:
                        related += [(post, db_post)]    # return existing value for field as well

        return related


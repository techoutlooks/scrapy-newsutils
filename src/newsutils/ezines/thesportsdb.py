"""
Utility classes for pulling sport news from the `thesportsdb.com`
into the configured database.
"""
import datetime
from collections import Counter

import requests
import scrapy
from bson import ObjectId

from daily_query.mongo import Collection
from itemadapter import ItemAdapter
from ratelimit import sleep_and_retry, limits

from newsutils.conf import UNKNOWN, get_setting
from newsutils.conf.mixins import SportsConfigMixin


__all__ = [
    "SportEvent", "BaseSports", "SchedulesMixin", "Sports",
    "SPORTS", "SPORTS_LEAGUES_MAP"
]


# static settings for querying the free api at `thesportsdb.com`
# inspired from `https://github.com/TralahM/thesportsdb`
# Free users, can use the test API key "3" during development
# $5/mo Patreon get a dedicated production API key with special features.
# send no more than 1 API request per 2 seconds
API_KEY = 3
BASE_URL = "https://www.thesportsdb.com/api/v1/json/"
LEAGUE_SEASON_EVENTS = "/eventsseason.php"
SPORTS = {
    "102": {
        "idSport": "102",
        "strSport": "Soccer",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/soccer.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "103": {
        "idSport": "103",
        "strSport": "Motorsport",
        "strFormat": "EventSport",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/motorsport.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "104": {
        "idSport": "104",
        "strSport": "Fighting",
        "strFormat": "EventSport",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/fighting.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "105": {
        "idSport": "105",
        "strSport": "Baseball",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/baseball.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "106": {
        "idSport": "106",
        "strSport": "Basketball",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/basketball.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "107": {
        "idSport": "107",
        "strSport": "American Football",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/american_football.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "108": {
        "idSport": "108",
        "strSport": "Ice Hockey",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/ice_hockey.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "109": {
        "idSport": "109",
        "strSport": "Golf",
        "strFormat": "EventSport",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/golf.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "110": {
        "idSport": "110",
        "strSport": "Rugby",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/rugby.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "111": {
        "idSport": "111",
        "strSport": "Tennis",
        "strFormat": "EventSport",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/tennis.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "112": {
        "idSport": "112",
        "strSport": "Cricket",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/cricket.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "113": {
        "idSport": "113",
        "strSport": "Cycling",
        "strFormat": "EventSport",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/cycling.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "114": {
        "idSport": "114",
        "strSport": "Australian Football",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/australian_football.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "115": {
        "idSport": "115",
        "strSport": "ESports",
        "strFormat": "EventSport",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/esports.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "116": {
        "idSport": "116",
        "strSport": "Volleyball",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/volleyball.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "117": {
        "idSport": "117",
        "strSport": "Netball",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/netball.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "118": {
        "idSport": "118",
        "strSport": "Handball",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/handball.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "119": {
        "idSport": "119",
        "strSport": "Snooker",
        "strFormat": "EventSport",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/snooker.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "120": {
        "idSport": "120",
        "strSport": "Field Hockey",
        "strFormat": "TeamvsTeam",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/Field_Hockey.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
    "121": {
        "idSport": "121",
        "strSport": "Darts",
        "strFormat": "EventSport",
        "strSportThumb": "https://www.thesportsdb.com/images/sports/Darts.jpg",
        "strSportThumbGreen": "https://www.thesportsdb.com/images/sports/motorsport_green2.jpg",
    },
}
SPORTS_LEAGUES_MAP = {
    "102": [
        "4328",
        "4329",
        "4330",
        "4331",
        "4332",
        "4334",
        "4335",
        "4336",
        "4337",
        "4338",
        "4339",
        "4340",
        "4344",
        "4346",
        "4347",
        "4350",
        "4351",
        "4354",
        "4355",
        "4356",
        "4358",
        "4359",
        "4367",
        "4394",
        "4395",
        "4396",
        "4397",
        "4398",
        "4399",
        "4400",
        "4401",
        "4403",
        "4404",
        "4406",
        "4422",
        "4429",
        "4432",
        "4435",
        "4457",
        "4472",
        "4480",
        "4481",
        "4482",
        "4483",
        "4484",
        "4485",
        "4490",
        "4496",
        "4497",
        "4498",
        "4499",
        "4500",
        "4501",
        "4502",
        "4503",
        "4504",
        "4505",
        "4506",
        "4507",
        "4509",
        "4510",
        "4511",
        "4512",
        "4513",
        "4519",
        "4520",
        "4521",
        "4523",
        "4524",
        "4525",
        "4526",
        "4562",
        "4565",
        "4566",
        "4569",
        "4570",
        "4571",
        "4590",
        "4616",
        "4617",
        "4618",
        "4619",
        "4620",
        "4621",
        "4622",
        "4623",
        "4624",
        "4625",
        "4626",
        "4627",
        "4628",
        "4629",
        "4630",
        "4631",
        "4632",
        "4633",
        "4634",
        "4635",
        "4636",
        "4637",
        "4638",
        "4639",
        "4640",
        "4641",
        "4642",
        "4643",
        "4644",
        "4645",
        "4646",
        "4647",
        "4648",
        "4649",
        "4650",
        "4651",
        "4652",
        "4653",
        "4654",
        "4655",
        "4656",
        "4657",
        "4659",
        "4661",
        "4662",
        "4663",
        "4665",
        "4666",
        "4667",
        "4668",
        "4669",
        "4670",
        "4671",
        "4672",
        "4673",
        "4674",
        "4675",
        "4676",
        "4677",
        "4678",
        "4679",
        "4681",
        "4682",
        "4683",
        "4684",
        "4685",
        "4686",
        "4687",
        "4688",
        "4689",
        "4690",
        "4691",
        "4692",
        "4693",
        "4694",
        "4695",
        "4713",
        "4719",
        "4720",
        "4721",
        "4723",
        "4724",
        "4725",
        "4739",
        "4741",
        "4742",
        "4743",
        "4744",
        "4745",
        "4746",
        "4747",
        "4748",
        "4749",
        "4750",
        "4751",
        "4752",
        "4753",
        "4754",
        "4755",
        "4756",
        "4757",
        "4778",
        "4779",
        "4780",
        "4782",
        "4783",
        "4784",
        "4785",
        "4786",
        "4788",
        "4789",
        "4790",
        "4791",
        "4792",
        "4793",
        "4794",
        "4795",
        "4796",
        "4797",
        "4802",
        "4803",
        "4804",
        "4805",
        "4806",
        "4811",
        "4812",
        "4813",
        "4814",
        "4815",
        "4816",
        "4817",
        "4818",
        "4819",
        "4820",
        "4821",
        "4822",
        "4823",
        "4824",
        "4825",
        "4826",
        "4827",
        "4828",
        "4829",
        "4834",
    ],
    "103": [
        "4370",
        "4371",
        "4372",
        "4373",
        "4393",
        "4407",
        "4409",
        "4410",
        "4411",
        "4412",
        "4413",
        "4436",
        "4437",
        "4438",
        "4439",
        "4440",
        "4447",
        "4454",
        "4466",
        "4468",
        "4469",
        "4486",
        "4487",
        "4488",
        "4489",
        "4522",
        "4564",
        "4573",
        "4576",
        "4587",
        "4588",
        "4712",
        "4730",
        "4732",
    ],
    "104": [
        "4443",
        "4444",
        "4445",
        "4448",
        "4449",
        "4450",
        "4451",
        "4453",
        "4455",
        "4467",
        "4491",
        "4492",
        "4493",
        "4494",
        "4495",
        "4563",
        "4567",
        "4593",
        "4594",
        "4595",
        "4596",
        "4597",
        "4598",
        "4599",
        "4600",
        "4601",
        "4602",
        "4603",
        "4604",
        "4605",
        "4608",
        "4609",
        "4610",
        "4611",
        "4612",
        "4613",
        "4614",
        "4696",
        "4697",
        "4698",
        "4699",
        "4700",
        "4701",
        "4702",
        "4703",
        "4704",
        "4705",
        "4706",
        "4708",
        "4709",
        "4710",
        "4711",
        "4726",
        "4727",
        "4728",
        "4729",
        "4735",
        "4736",
        "4737",
        "4787",
        "4798",
        "4799",
        "4800",
        "4807",
        "4840",
        "4843",
    ],
    "105": ["4424", "4427", "4428", "4591", "4592", "4830", "4837"],
    "106": [
        "4387",
        "4388",
        "4408",
        "4423",
        "4431",
        "4433",
        "4434",
        "4441",
        "4442",
        "4452",
        "4474",
        "4475",
        "4476",
        "4477",
        "4478",
        "4516",
        "4518",
        "4546",
        "4547",
        "4548",
        "4549",
        "4577",
        "4578",
        "4579",
        "4580",
        "4607",
        "4734",
        "4831",
        "4832",
        "4833",
        "4836",
    ],
    "107": [
        "4391",
        "4405",
        "4470",
        "4471",
        "4473",
        "4479",
        "4552",
        "4718",
        "4809",
        "4839",
    ],
    "108": ["4380", "4381", "4419", "4738", "4810", "4838"],
    "109": [
        "4425",
        "4426",
        "4553",
        "4740",
        "4758",
        "4759",
        "4760",
        "4761",
        "4762",
        "4763",
        "4764",
        "4765",
        "4766",
        "4767",
        "4768",
        "4769",
        "4770",
        "4771",
        "4772",
        "4773",
        "4774",
        "4775",
        "4776",
        "4777",
    ],
    "110": [
        "4414",
        "4415",
        "4416",
        "4417",
        "4430",
        "4446",
        "4550",
        "4551",
        "4574",
        "4589",
        "4714",
        "4722",
    ],
    "111": ["4464", "4517", "4581"],
    "112": [
        "4458",
        "4459",
        "4460",
        "4461",
        "4462",
        "4463",
        "4575",
        "4801",
        "4808",
        "4841",
        "4844",
    ],
    "113": ["4465"],
    "114": ["4456"],
    "115": [
        "4515",
        "4528",
        "4529",
        "4530",
        "4531",
        "4532",
        "4568",
        "4715",
        "4716",
        "4717",
    ],
    "116": ["4542", "4543", "4544", "4545", "4582", "4583", "4584"],
    "117": ["4538", "4539", "4540", "4541", "4842"],
    "118": ["4533", "4534", "4535", "4536", "4537"],
    "119": ["4555"],
    "120": ["4558", "4559", "4560", "4585", "4586"],
    "121": ["4554", "4561"],
}


# DEFAULT_SPORTS_IDS    : cf. `thesportsdb.settings.SPORTS`. eg. Soccer=102, Basketball=106
# EVENT_ID_FIELDS       : compound primary key to generate the `_id` key
DEFAULT_SPORTS_IDS = [102, 106]
EVENT_ID_FIELDS = 'idLeague', 'idHomeTeam', 'idAwayTeam', 'idEvent'


rate_limit = get_setting('SPORTS.rate_limit', int)
fetch_limit = get_setting('SPORTS.fetch_limit', int)
timeout = get_setting('SPORTS.timeout', int)


class SportEvent(scrapy.Item):

    _id = scrapy.Field()

    idEvent = scrapy.Field()
    idSoccerXML = scrapy.Field()
    idAPIfootball = scrapy.Field()
    strEvent = scrapy.Field()
    strEventAlternate = scrapy.Field()
    strFilename = scrapy.Field()
    strSport = scrapy.Field()
    idLeague = scrapy.Field()
    strLeague = scrapy.Field()
    strSeason = scrapy.Field()
    strDescriptionEN = scrapy.Field()
    strHomeTeam = scrapy.Field()
    intAwayScore = scrapy.Field()
    strAwayTeam = scrapy.Field()
    intRound = scrapy.Field()
    intHomeScore = scrapy.Field()
    intSpectators = scrapy.Field()
    strOfficial = scrapy.Field()
    strTimestamp = scrapy.Field()
    dateEvent = scrapy.Field()
    dateEventLocal = scrapy.Field()
    strTime = scrapy.Field()
    strTimeLocal = scrapy.Field()
    strTVStation = scrapy.Field()
    idHomeTeam = scrapy.Field()
    idAwayTeam = scrapy.Field()
    intScore = scrapy.Field()
    intScoreVotes = scrapy.Field()
    strResult = scrapy.Field()
    strVenue = scrapy.Field()
    strCountry = scrapy.Field()
    strCity = scrapy.Field()
    strPoster = scrapy.Field()
    strSquare = scrapy.Field()
    strFanart = scrapy.Field()
    strThumb = scrapy.Field()
    strBanner = scrapy.Field()
    strMap = scrapy.Field()
    strTweet1 = scrapy.Field()
    strTweet2 = scrapy.Field()
    strTweet3 = scrapy.Field()
    strVideo = scrapy.Field()
    strStatus = scrapy.Field()
    strPostponed = scrapy.Field()
    strLocked = scrapy.Field()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['_id'] = self.mkoid()

    def mkoid(self):
        """ Generate a predictable (not random) oid
        suitable for db upserts """
        oid = str.encode("".join([self[n] for n in EVENT_ID_FIELDS])[:12])
        return ObjectId(oid)


@sleep_and_retry
@limits(calls=1, period=datetime.timedelta(seconds=rate_limit).total_seconds())
def fetch(endpoint: str, **kwargs):
    """
    TheSportsDB free API key requires sending no more than 1 API request per 2 seconds
    """
    params = kwargs
    url = BASE_URL + str(API_KEY) + endpoint
    try:
        r = requests.get(url, timeout=timeout, params=params)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("fetch error:", e)
        return dict(events=None)

    return r.json()


class BaseSports(SportsConfigMixin, Collection):
    """
    Base building block for saving various sport news information
    types fetched from https://thesportsdb.com to the database.
    One sport per collection!
    """

    sports_ids: [str] = DEFAULT_SPORTS_IDS

    @property
    def season(self):
        y = datetime.date.today().year
        this_season = f"{y}-{y + 1}"
        return getattr(self, '_season', this_season)

    @season.setter
    def season(self, value: str):
        setattr(self, '_season', value)

    def __init__(self, sports_ids=None, season=None, limit=fetch_limit):

        # initialises a temporary collection named `_default`
        super().__init__(db_or_uri=self.db_uri)

        if sports_ids:
            self.sports_ids = sports_ids
        self.season = season
        self.limit = limit


class SchedulesMixin:
    """
    Mixin for fetching match schedules for given sports and season,
    and saving them to the database.

    Usage:

        # with default settings, fetches to the db current season's matches
        # for Soccer=102, Basketball=106.
        class Sports(BaseSports, FetchSportsMixin):
            pass

        sports = Sports()
        sports.save_all()

    """

    def fetch_sports(self):
        """
        All events in specific league by season (Free tier limited to 100 events)
        https://www.thesportsdb.com/api.php

        # work only with dev key='2', without being a Patreon.
        # eg. fetch `La Liga` (league_id=4335) matches schedule:
        # https://www.thesportsdb.com/api/v1/json/2/eventsseason.php?id=4335&s=2022-2023
        # https://www.thesportsdb.com/league/4335-Spanish-La-Liga

        """
        counter = Counter()
        season = self.season
        for sport_id in self.sports_ids:
            sport_id = str(sport_id)
            leagues_ids = SPORTS_LEAGUES_MAP.get(str(sport_id))
            for league_id in leagues_ids:

                if counter[sport_id] > self.limit:
                    break

                r = fetch(LEAGUE_SEASON_EVENTS, id=str(league_id), s=season)
                events = r.get('events', [])
                if events:
                    for data in events:
                        counter.update([sport_id])
                        event = SportEvent(data)
                        yield event

    def save(self, event: SportEvent):
        """
        Save event under collection by the sport name (lowercased)
        """

        _post, saved = None, 0
        log_msg = lambda detail: \
            f"saving event (sport `{event.get('strSport') or UNKNOWN}`) #" \
            f"{event.get(self.db_id_field, event['idEvent'])} to db: " \
            f"{detail}"

        try:
            adapter = ItemAdapter(event)
            _id = ObjectId(adapter.item.get(self.db_id_field, None))
            adapter.update({self.db_id_field: _id})

            collection_name = adapter.item.get('strSport').lower()
            r = self(collection_name).update_one(
                {'_id': {'$eq': _id}}, {"$set": adapter.asdict()}, upsert=True)
            _post, saved = adapter.item, r.modified_count

            # log
            op = 'inserted' if r.upserted_id else 'updated'
            self.log_ok(log_msg, f"{op} ({r.modified_count}/{r.matched_count})")

        except Exception as exc:
            self.log_failed(log_msg, exc, '')

        return _post, saved

    def save_all(self):
        for event in self.fetch_sports():
            self.save(event)


class Sports(BaseSports, SchedulesMixin):
    pass


# testing
if __name__ == '__main__':

    sports = Sports()
    sports.save_all()




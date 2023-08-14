import os

import pytest


sa_json = "/home/ceduth/Devl/Projects/Leeram/leeram-51c8a2d9d33a.json"
os.environ['SCRAPY_SETTINGS_MODULE'] = 'scrapy.settings'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = sa_json


@pytest.fixture
def media_storage():
    # from newsutils.conf import get_setting
    # return get_setting("MEDIA_STORAGE")
    return 'leeram-news'


def test_upload_blob_from_url(media_storage):
    from newsutils.storage import upload_blob_from_url

    url = "https://unsplash.com/photos/hteGzeFuB7w"
    upload_blob_from_url(url, media_storage)

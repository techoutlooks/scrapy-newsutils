from newsutils.appsettings import AppSettings
from newsutils.helpers import get_env


__all__ = (
    "configure_ezines",
    "Sports"
)


# Dotted path to Project settings module.
# eg. SCRAPY_SETTINGS_MODULE=crawl.settings
settings_module = get_env('SCRAPY_SETTINGS_MODULE')


def configure_ezines(**kwargs):

    s = Sports(**kwargs)
    s = s(settings_module, 'scrapy.settings.default_settings')
    return s.settings


class Sports(AppSettings):

    SPORTS = {
        'timeout': 1,
        'rate_limit': 3,
        'fetch_limit': 100
    }



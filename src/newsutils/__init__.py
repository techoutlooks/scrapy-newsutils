from .appsettings import AppSettings
from .logging import *


# module globals
# _settings: project settings cache. populated by merely importing this module
__version__ = '0.0.1'
__title__ = 'newsutils'
_settings = dict()


def get_project_settings():
    """
    Patches merged settings (project-defined, this lib's defaults, scrapy defaults),
    inside os.sys['*.settings'] and os.sys['*.default_settings']
    Results in following call returning merged settings:
        `from scrapy.utils.project import get_project_settings`

    Usage:

        This is enough to perform the merge/patching:
        >>> import newsutils

        Client code can also make following call to return cached (merged) settings:
        >>> from newsutils.scrapy import get_project_settings
        >>> setting = get_project_settings()

    """
    from .scrapy.base import get_scrapy_settings

    global _settings
    if not _settings:
        _settings.update(get_scrapy_settings())
    return _settings


# on importing this module,
# patch load and patch scrapy settings once
get_project_settings()


class BaseConfigMixin(TaskLoggerMixin):
    """ Mixin. Exposes utility class attributes. """

    # the project's settings module will get automagically patched
    # by the `newsutils`library, on import, with useful defaults.
    # `default_settings = settings` required to prevent override of `.settings`
    # by the `cmdline.py` module when calling `.process_options()`
    settings = get_project_settings()  # FIXME: needed? delete since os.sys['settings'] already patched!
    default_settings = settings

    # DATABASE FIELDS
    # `item_id_field`: Identifies crawled items uniquely. NOT the database id.
    db_uri = settings["CRAWL_DB_URI"]
    db_id_field = settings['DB_ID_FIELD']


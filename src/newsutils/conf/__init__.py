import sys
from .settings import *


# module globals
# _settings: project settings cache. populated by merely importing this module
_project_settings = dict()
_already_configured = False


def get_project_settings(settings_module='settings'):
    if not _project_settings:
        raise Exception("Must call `configure()` first to initialize the `newsutils` library.")
    # return sys.modules[settings_module]
    return _project_settings


def configure():
    """
    Patches merged settings (project-defined, this lib's defaults, scrapy defaults),
    inside os.sys['*.settings'] and os.sys['*.default_settings']
    Results in following call returning merged settings:
        `from scrapy.utils.project import get_project_settings`

    Usage:

        Initialize settings first:
        >>> from newsutils.conf import configure
        >>> configure()

        Can also make following call to return cached (merged) settings:
        >>> from newsutils.conf import get_project_settings
        >>> setting = get_project_settings()

    """

    global _is_configured
    global _project_settings

    if not _already_configured:
        _project_settings.update(patch_scrapy_settings())
        # _settings.update(get_ezines_settings())
    else:
        raise Exception("`newsutils` module already initialized."
                        "You must call `configure()` exactly once!")






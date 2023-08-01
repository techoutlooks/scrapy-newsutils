"""
This modules contains primitives that merge settings from all sources
into a single  global variable `_project_settings` for internal use by the library.
This ensures that user-defined settings are captured by the library at runtime.

Note: Library users should define their settings in their `<scrapy-project>.settings` or
in env provided namespaces; and use them like so:
    >>> get_project_settings()['PUBLISH']

Settings are sought sequentially in :
- user-defined settings: env, then  `<scrapy-project>.settings`
- default settings: in config classes, ie. that subclass`newsutils.appsettings.AppSettings`
    cf. above path for implementation examples.

Currently, the following library modules use the depicted mechanism for loading their settings:
- `newsutils.crawl`
- `newsutils.ezines`

"""
from functools import reduce

from scrapy.utils.project import get_project_settings

from ..exceptions import ImproperlyConfigured

__all__ = (
    "configure", "get_setting"
)


# caches settings for apps defined by this library
# module global populated by merely importing this module
_is_configured = False


def configure():
    """
    Patches merged settings (project-defined && this lib's defaults && scrapy defaults),
    inside os.sys['*.settings'] AND os.sys['*.default_settings']
    Results in following call returning merged settings:
        `from scrapy.utils.project import get_project_settings`

    Project-defined settings module is as referenced by the `SCRAPY_SETTINGS_MODULE` (dotted module name).

    Usage:

        * First, initialize settings prior to using this library.
          Requires telling the library the project settings module location;
          eg., `export PROJET_SETTINGS_MODULE=demo.settings`

        >>> from newsutils.conf import configure
        >>> configure()

        * Get cached (merged) settings wherever needed in your code , ie:
        >>> setting = get_project_settings()

    """
    from .posts import configure_posts
    from .sports import configure_ezines

    global _is_configured
    if not _is_configured:
        _is_configured = \
            bool(configure_posts()) and bool(configure_ezines())

    else:
        raise ImproperlyConfigured(
            "`newsutils` module already initialized."
            "You may call `configure()` exactly once!")

    return _is_configured


def get_setting(keypath, cast=None):
    """
    Get a setting's value from its key's dotted-path name
    Assumes project_settings is a multilevel dict-like storage.

    :param str keypath: setting key, as a dotted path
        eg. "POSTS.similarity_siblings_threshold"
    """
    s = get_project_settings()
    root, *children = keypath.split(".")
    r = reduce(lambda _, key: _[key], children, s[root])
    return cast(r) if cast else r

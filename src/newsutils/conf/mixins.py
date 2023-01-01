from . import get_project_settings
from ..logging import TaskLoggerMixin


__all__ = ["BaseConfigMixin"]


class BaseConfigMixin(TaskLoggerMixin):
    """
    Mixin. Exposes utility class attributes.
    """

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
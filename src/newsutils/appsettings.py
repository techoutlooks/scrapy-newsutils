import abc
import copy
from importlib import import_module
from typing import List

from .exceptions import ImproperlyConfigured
from .helpers import camel_to_snake, get_env

__all__ = (
    "configure", "requires_configured",
    "AppSettings",
)


def configure(default_settings: dict, project_settings, project_default_settings,
              config_key: str = None, required_settings=[]):
    """
    Initializes a new app config with default settings from dict.
    Returned settings are merged (env/project/defaults) and patched in supplied
    framework's settings modules (project and framework's default).

    Following are AppSettings instance initialisers:
        :param default_settings: defaults settings, as class attributes with caps names
        :param config_key: setting key that hosts the app's own settings (config) dict
        :param required_settings: compulsory settings.

    Following are dotted names pointing to loaded settings modules to patch,
    These are settings modules recognised by the project's underlying framework.
        :param project_settings: project's settings module (eg. Django, Flask, Scrapy settings file)
        :param project_default_settings: framework's default builtin settings

    """

    # generate settings from create a anonymous AppSettings instance
    return type('', (AppSettings,), default_settings) \
        (config_key=config_key, required_settings=required_settings) \
        (project_settings, project_default_settings)


#
def requires_configured(validate_config=False):
    """ Method decorator: whether `.configured()` was ever called """

    def _requires_configured(method):
        def wrapper(self, *args, **kwargs):
            if not self.is_configured:
                raise Exception(err_msgs["not_configured"])
            if validate_config:
                config = self.settings.get(self.config_key)
                self._validate_config(config)
            return method(self, *args, **kwargs)

        return wrapper

    return _requires_configured


class AppSettings(metaclass=abc.ABCMeta):
    """
    Base class that has ability to make all subclasses have their capitalized
    class properties be injected into given loaded modules (by `sys.modules`)

    Obvious use case is for creating app-specific settings that override project settings.
    Settings priority: env -> project -> defaults

    project-defined settings: Package/Framework managed settings module,
        eg., settings module by Django, Flask, Scrapy, etc.

    app-specific settings: (aka. config) An app may define its own local settings
        with their default values, under the `config_key`. An app may also override a project
        -defined setting by providing its definition outside the `config_key`.


    **config_key**          Django setting's key that nests the app's config dict.
    **config**              The app's default settings as a dictionary
    **required_settings**  Keys of config items which must be defined explicitly
    **strict**             If True, raises an error if no config was found,

    - Nota: settings with value `None` are required, and must be explicitely defined,
        else an exception is raised.

    Usage:

        from djutils.appconfig import AppSettings
        class MyApp(AppSettings):

            # App-specific settings (aka. the app's `config`)
            # will be nested as a dict under the `MY_APP` config key
            # automatically detected, since it is named after the class.
            MY_APP = {
                'CONFIG_ITEM_1': 'Default config item One',
                'CONFIG_ITEM_2': 'Default config item Two'
                ...
            }

            # Site settings
            AUTH_USER = 'oneauth.User'


        # To inject the app settings into the project settings automatically,
        # either add to the app's `__init__.py`, or call `configure()` from
        #

        # my_app/__init__.py
        from my_app.settings import MyApp
        MyApp()

        # or

        # my_app/posts.py
        configure({
            AUTH_USER = 'oneauth.User'
            MY_APP = {
                'CONFIG_ITEM_1': 'Default config item One',
                'CONFIG_ITEM_2': 'Default config item Two'
            },
        }, 'MY_APP')

        # define computed settings, ie. settings that depend
        # on other configurable settings
        posts_config = settings.config
        posts_config["COMPUTED_ITEM"] = [
            CONFIG_ITEM_1,
            ...
        ]


        # Config class initialization
        # Possible to specify a config_key explicitly, if should differ from
        # the camelcased name of the config class.
        >>> my_app_settings = MyApp()
        >>> my_app_settings = MyAppSettings(config_key="MY_APP")

        # Accessing config values
        >>> my_app_settings.config_key
        'MY_APP'
        >>> my_app_settings.settings
        {'SETTING_ONE': 'Setting One', 'SETTING_TWO': 'Setting Two'}


        # FIXME: class properties not patched, eg. self.POSTS, etc.
        # FIXME: force
        # TODO: load/parse config from `.cfg` file.
            cf. configparser
                https://gitlab1.cs.cityu.edu.hk/gsalter2/dockers/-/blob/37836f254c8fcc10f70b991eb0c6f5c31378bcb4/manim/manim/_config/utils.py

    """

    _project_settings = None
    _project_default_settings = None
    _refresh = False  # `_refresh` triggers re-computing settings
    _signal_registry: list = []

    def __init__(self, config_key=None, required_settings=None, strict=True, priority='project'):
        """

        :param config_key:
        :param required_settings:
        :param strict:
        """

        # prop methods.
        self._defaults = {}  # cache, default settings from this class
        self._settings = {}  # cache, live settings, source of truth
        self._config_key = config_key
        self.is_configured: bool = False  # was `.configure()` ever called?

        self.strict, self.priority, self.required_settings = \
            (strict, priority, list(required_settings)
            if isinstance(required_settings, (dict, list, tuple)) else [])

    def __call__(self, project_settings, project_default_settings):
        self.configure(project_settings, project_default_settings)
        for fn in self._signal_registry:
            fn(self.settings)
        return self

    def __getitem__(self, key):
        """
        Get an app-defined setting's value lazily by name.
        Lookups app-specific settings first (app's config), then global (site's)
         settings defined within the app

        Raises `ImproperlyConfigured`, if the setting is required to be explicitly
        defined, ie., in the project's `day.py`.
        """
        setting = self.config.get(key, self.settings.get(key, None))
        if key in self.required_settings and not setting:
            raise ImproperlyConfigured(
                f'Required `{self.config_key}["{key}"]` has no defaults, '
                f'thus must be defined explicitly.')
        return setting

    def __setitem__(self, key, value):
        """ Actualise project settings """
        self._settings[key] = value
        self.inject(**{key: value})

    @property
    def has_config(self):
        """ Whether the config class defines an app-specific settings dict """
        return self.config_key in self.defaults

    @property
    def defaults(self):
        """
        Default settings, ie. all class members with capital names
        in this class definition
        """
        if self._defaults:
            return self._defaults
        return self.asdict()

    def asdict(self):
        """ Return this settings object as a dict. """
        return dict((key, value) for (key, value) in type(self).__dict__.items()
                    if not key.startswith('__') and not key.islower())

    @property
    def settings(self):
        """
        Live project settings. The source of truth.
        Merges the env, the project and the app settings with following override priority:
        env > project settings > app's defaults iff priority=='project'
        defaults > env > project settings iff priority=='cmdline'

        Nota: env is expected to be priorly set as an uppercase class property
        cf. https://pypi.org/project/python-environ/
            eg. POSTS=metapost_baseurl\=http://localhost:3100/post
        """

        # return locally cached settings if existed and refresh not requested
        # TODO: on settings changed signal, clear cache and recompute
        if self._settings and not self._refresh:
            return self._settings

        for key in self.defaults:

            # deepcopy: to ensure no mere ref of defaults dict is passed as a live setting.
            # settings lookup policy: env, then user-configured project settings, then default settings.
            # settings merging policy: app's default config => update, others => override.
            # with `coerce=True`, requires env var to be of the same type as the setting's default value.
            _default: dict = copy.deepcopy(self.defaults[key])
            _override = get_env(key, getattr(self._project_settings, key, _default), coerce=True)

            # swap
            if self.priority == 'cmdline':
                _ = _override
                _override, _default = _default, _

            if key == self.config_key:
                self._validate_config(_override)
                _default.update(_override)
                self._settings[key] = _default
            else:
                self._settings[key] = _override

            # required settings have to be explicitly defined. thus, an
            # exception is raised if required settings were found nowhere.
            self.fail_required(key, self.settings[key])

        return self._settings

    def configure(self, project_settings, project_default_settings):
        """
        Configure the project, ie., loads candidate settings modules and
        injects them with settings defined on this class.
        """
        if not self.has_config and self.strict:
            raise KeyError(err_msgs['config_not_found'] % {
                "cls_name": {type(self).__name__}, 'config_key': self.config_key})

        # import project settings modules
        # ImportError thrown if module import fails
        for (name, mod) in {
            "_project_settings": project_settings,
            "_project_default_settings": project_default_settings
        }.items():
            setattr(self, name, import_module(mod))

        self.inject()
        self.is_configured = True

    def inject(self, **kwargs):
        """
        Inject the app defined settings into the project and framework settings modules.
        Works by patching loaded settings modules from `sys.modules`.
        Low-level method: consumers should call rather call `.configure()`.

        https://passingcuriosity.com/2010/default-settings-for-django-applications/
        https://docs.djangoproject.com/en/3.1/topics/settings/
        """
        for k, v in (kwargs or self.settings).items():
            setattr(self._project_default_settings, k, v)
            setattr(self._project_settings, k, v)

    # APP CONFIG
    # ----------

    @property
    def config_key(self):
        # don't re-compute the config key if was done once
        # or unless requested expressly (`_refresh` == True)
        if not (self._refresh or not self._config_key):
            return self._config_key

        self._config_key = self._config_key or \
                           camel_to_snake(type(self).__name__).upper()

        if not hasattr(type(self), self._config_key):
            raise KeyError(err_msgs["config_key_missing"] % {
                "cls_name": type(self).__name__, "config_key": self.config_key,
            })

        return self._config_key

    @property
    @requires_configured(validate_config=True)
    def config(self):
        """
        App-specific settings (live ones!) under the config key.
        :raises ValueError if validation fails.
        """
        config = self.settings.get(self.config_key)
        return config

    def _validate_config(self, config) -> bool:
        """ Default config validator. If implementation defines a
         `.validate_config()`, call it as well """

        if not isinstance(config, dict):
            raise ValueError(err_msgs["config_not_dict"] % {
                "config_key": self.config_key, "config_value": config})

        if hasattr(self, 'validate_config'):
            return self.validate_config(config)

        return True

    def fail_required(self, key, value: dict):
        """
        Fail required settings
        A setting with value `None` is a required setting.
        """
        required_keys = ()
        if isinstance(value, dict):
            required_keys = list(dict(filter(lambda s: s[1] is None, value.items())))
        if value is None:
            required_keys = [key]

        if len(required_keys):
            raise ImproperlyConfigured(err_msgs['config_required_settings'] % {
                "keys": ", ".join(required_keys)
            })


err_msgs = {
    "not_configured":
        "Settings not configured. Was `.configured()` ever called?",

    "config_not_found":
        f"Class %(cls_name)s declares no app config. "
        f"Strict mode requires defining your app's settings, "
        "eg. `%(config_key)s: {...}`",

    "config_key_missing":
        "Missing config key for settings class `%(cls_name)s`.\n"
        "Hint: `%(cls_name)s(config_key=%(config_key)s)`",

    "config_not_dict":
        "Config value for %(config_key)s must be `dict`, got: %(config_value)s.\n"
        "Hint: `%(config_key)s = %(config_value)s)`",

    "config_required_settings":
        "The %(keys)s setting(s) must not be empty!"

}

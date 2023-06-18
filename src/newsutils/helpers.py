import re
import unicodedata
from functools import reduce
from importlib import import_module

from environs import Env

# == [CONSTANTS] ==


# `read_env()` is to allow reading from .env file
env = Env()
env.read_env()


DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = f'{DATE_FORMAT} %H:%M:%S'


# == [UTILS] ==

# like `.get("key")` method of dict, but supports dotted path as "key"
# eg. getdeep(body, "error.error_user_msg")
getdeepattr = lambda obj, path: \
    reduce(lambda v, k: getattr(v, k, None), path.split("."), obj)


# like `.get("key")` method of dict, but supports dotted path as "key"
# eg. getdeep(body, "error.error_user_msg")
# don't raise if key not found but return {}, which evals to None ;)
getdeep = lambda obj, path: \
    reduce(lambda v, k: v.get(k, {}), path.split("."), obj)


hexoint = lambda hex: f"0x{str(hex)}"

# facilitate regular set operations (union, difference, etc.),
# on list of dicts
# facilitate regular set operations (union, difference, etc.),
# on list of dicts
dictlist_factory = lambda op: lambda *dict_lists: reduce(
    lambda l1, l2: [dict(s) for s in
                    getattr({*[frozenset(d.items()) for d in l1]}, op)
                        (frozenset(d.items()) for d in l2)],
    dict_lists
)


evalfn = lambda f: f()


# difference and union of lists of dicts,
# eg. dictdiff([d_11, d_12, ...], [d_21, d_22, ...], ...)
dictdiff = dictlist_factory('difference')
dictunion = dictlist_factory('union')


# get unique dicts (flatten list) from list of dicts.
# solves error: `{TypeError}unhashable type: 'dict'` yielded by
# the **set(dict)** construct, cf. https://stackoverflow.com/a/38521207
# by freezing every dict (all items in dict at once) !
uniquedicts = lambda *dict_lists: reduce(lambda l1, l2: [
    dict(s) for s in {*[frozenset(d.items()) for d in l1],
                      *[frozenset(d.items()) for d in l2]}
], dict_lists)


# compose any number of functions in given order
# usage: compose(fn1, fn2)(x)
compose = lambda *fns: reduce(lambda f, g: lambda x: f(g(x)), fns)

# similar to JS's Array.prototype.flatMap()
# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/flatMap
flatmap = lambda f, xs: (y for ys in xs for y in f(ys))


# == [TEXT] ==


wordcount = lambda sent: len(sent.split(" "))


def add_fullstop(sent: str):
    """ add fullstop to sentence. """
    if not sent:
        return ""
    return sent if any([sent.endswith(_) for _ in ".!?…"]) \
        else sent + "."


def camel_to_snake(name):
    """
    LeeramNews -> leeram_news
    """
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def to_camel(word):
    """ From any case to CamelCase """
    return ''.join(x.capitalize() for x in re.split(r'\W+', word))


def remove_diacritics(text):
    """
    Returns a string with all diacritics (aka non-spacing marks) removed.
    For example "Héllô" will become "Hello".
    Useful for comparing strings in an accent-insensitive fashion.
    https://stackoverflow.com/a/35783136
    """
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


# == [SYS] ==

def get_env(name, *args, coerce=None) -> str:
    """
    Get the value for environment variable <name>.
    Takes the default value as only positional arg.
    Raises if variable <name> is not set and no default is supplied.

    * Uses environs => dotenv packages for env parsing.

    :param str name: env name
    :param bool|str coerce: whether to require env var to assume a certain type
        coerce==False: dismiss type casting. similar to using `env()`
        coerce==True: auto-detection of casting type
        type(coerce)==string: requires type casting method name
            eg. 'int'|'str'|'bool'|'dict', etc.
            cf. https://pypi.org/project/environs/#supported-types
    """

    # at most single arg after env name
    assert len(args) < 2, \
        "`get_env()` supports at most two positional arguments: " \
        "eg., get_env('ENV_VAR_NAME', default_value, coerce=dict)"

    # coerce must either be supported casting type from the environs package,
    # or coerce==True => sniff cast type from default value (auto mode)
    typecast = coerce
    if coerce:
        if len(args) and coerce is True:
            default = args[0]
            typecast = type(default).__name__
        assert hasattr(env, typecast), \
            f"{coerce} is no supported type-casting methods of Env!" \
            f"Cf. https://pypi.org/project/environs/#supported-types."

    _get_env = getattr(env, typecast) \
        if coerce else env

    return _get_env(name, *args)


def import_attr(path):
    """
    Import a module attribute (eg. constant, function, or class)
    dynamically from its dotted path

    :param path: setting name, as a dotted path.
    """
    # dot_pos = path.rfind('.')
    # module, attr = path[:dot_pos], path[dot_pos + 1:]
    module, attr = path.rsplit(".", 1)
    try:
        mod = import_module(module)
        cls = getattr(mod, attr)
    except (ImportError, ValueError) as err:
        raise ImportError('Error importing module %s: "%s"' % (path, err))
    except AttributeError:
        raise ImportError('Module "%s" does not define a "%s" attribute' % (module, attr))
    return cls


def import_module_custom(module):
    """
    Get module (by str or module) ref?? from sys.modules
    mocks importlib.import_module
    """
    import sys
    import inspect

    if isinstance(module, str):
        module = sys.modules.get(module)
    if not inspect.ismodule(module):
        raise ImportError(f"Can't import settings {module}")
    return module



# == [DECORATORS] ==


class classproperty(object):

    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


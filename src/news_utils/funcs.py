import os
import re
from functools import reduce
from importlib import import_module


# == [CONSTANTS] ==


DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = f'{DATE_FORMAT} %H:%M:%S'


# == [DATA] ==


hexoint = lambda hex: f"0x{str(hex)}"

# facilitate regular set operations (union, difference, etc.),
# on list of dicts
dictlist_factory = lambda op: lambda *dict_lists: \
    reduce(lambda l1, l2: [dict(s) for s in
                       getattr({*[frozenset(d.items()) for d in l1]}, op)
                       (frozenset(d.items()) for d in l2)],
           dict_lists)


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
    AriseNews -> arise_news
    """
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


# == [SYS] ==


def get_env_variable(name, default=None) -> str:
    try:
        return os.environ[name]
    except KeyError:
        if default is not None:
            return default
        message = "Expected environment variable '{}' not set.".format(name)
        raise Exception(message)


def import_class(path):
    """
    Import class dynamically from dotted module path
    """
    dot_pos = path.rfind('.')
    module, attr = path[:dot_pos], path[dot_pos + 1:]
    try:
        mod = import_module(module)
    except (ImportError, ValueError) as err:
        raise ImportError(
            'Error importing module %s: "%s"' % (path, err))
    try:
        cls = getattr(mod, attr)
    except AttributeError:
        raise ImportError('Module "%s" does not define a "%s" class' % (module, attr))
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


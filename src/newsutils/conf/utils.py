import collections
from dataclasses import dataclass

import scrapy
from .constants import ARGS_SEP


__all__ = [
    "ItemValue", "Item",
    "mkdefaults", "validate_fields", "args_from_str"
]


# create default settings as a datadaclass
# dotted attribute access guarantees we don't mistype field names.
mkdefaults = lambda defaults: \
    dataclass(type("defaults", (), defaults))


# basic field type detection heuristic from field names that
# follow naming conventions: is_* -> bool, *s -> plural, etc.
is_plural = lambda w: w.endswith('s') and not w.endswith('ss')
is_bool = lambda w: w.startswith('is_')


# cmd's string args  -> [args]
args_from_str = lambda s: s.split(ARGS_SEP) if s else s


def validate_fields(src: [str], valid_list: [str], raise_exc=True):
    """
    Extract valid unique fields from `src` (source of truth: `valid_list`).
    Returns `valid_list` if src is None.
    Raises if validation fails and `raise_exc` is set,
    """

    valid = list(set(src or []).intersection(valid_list or []))
    if not valid:
        if src and raise_exc:
            assert valid, f"Unsupported fields(s): {src}. " \
                          f"Valid fields: {', '.join(valid_list)}"
        return valid_list
    return valid


class ItemValue(collections.UserDict):
    """
    `defaultdict` that guesses the default value to return for non-existing keys
    based on the variable's name.

    Provider for values to be set on the `scrapy.Item` instances,
    Impl. as a dict container in similar manner as `collections.defaultdict`,
    but able to initialize default values by guessing their resp. key type,
    ie.
        pluralized key (eg. 'authors') ->  initialized to []
        key starting with `is_` (eg. 'is_draft') -> bool, initialized to False

    Priority for resolving values :
        inventory -> heuristics -> default_factory -> raises KeyError
    """

    # behavior if the builtin heuristics find no default value for any given field
    # `NO_DEFAULT`: return `None` if no default was found for the field
    # `REQUIRES_DEFAULT`: raises KeyError is no default was found for the key
    NO_DEFAULT = lambda: None
    REQUIRES_DEFAULT = None

    def __init__(self, default_factory=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not callable(default_factory) and default_factory is not None:
            raise TypeError('first argument must be callable or None')
        self.default_factory = default_factory

    def __missing__(self, key: str):
        if self.default_factory is None:
            raise KeyError(key)

        if key not in self:
            if is_plural(key):
                self[key] = []
            elif is_bool(key):
                self[key] = False
            else:
                self[key] = self.default_factory() if \
                    self.default_factory else None

        return self[key]


class Item(scrapy.Item):
    """ Enhanced Item
        - Supports setting default values for scrapy fields,
    """
    def __init__(self, *args, defaults: ItemValue = None, **kwargs):
        super().__init__(*args, **kwargs)

        # set default values for all fields
        if defaults:
            for n in list(self.fields):
                if isinstance(self.fields[n], scrapy.Field):
                    self[n] = self.get(n, defaults[n])


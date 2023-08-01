#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
import logging
import string
from functools import reduce
from typing import List, Callable

from rich.console import OverflowMethod
from rich.logging import RichHandler
from newsutils.console import make_logger

from newsutils.console import console


__all__ = [
    "LoggingMixin", "TaskLoggerMixin", "NamespaceFormatter", "log_running",
    "OK", "FAILED", "STARTED", "DONE", "TASK_ENDED", "TASK_RUNNING",
    "PADDING", "PADDING_INTERNAL", "SEP_LINE"
]

# message statuses
# https://carpedm20.github.io/emoji/
OK = ":OK_hand: OK "
FAILED = ":broken_heart: FAILED "
STARTED = ":next_track_button: STARTED "
DONE = ":stop_button: DONE "
TASK_ENDED = ":hundred_points: "
TASK_RUNNING = ":running_shoe: RUNNING "

PADDING_INTERNAL = 20
PADDING = 10
SEP_LINE = '-' * 70


def log_running(
    title=None,
    description=None,
    overflow: List[OverflowMethod] = "ellipsis",
    style="bold white on blue"
):
    """
    Decorator that logs a running task
    eg.
        @log_running('a static msg ...')
        def crawl(self, spider, *args, **kwargs):
            return self.runner.crawl(spider, *args, **kwargs)
    """

    def _log_running(task):
        def wrapper(self, *args, **kwargs):
            with self.console.status(title, spinner="monkey"):
                self.console.rule(f"[bold blue]{title}")
                if description:
                    self.log_task(logging.INFO, TASK_RUNNING, description, overflow=overflow, style=style)
                r = task(self, *args, **kwargs)
                self.console.print()
                return r
        # yields a stub that picks the decorated
        # method's params, and call it
        return wrapper
    # yields the actual decorator, called like so:
    # log_running(header=None, ...)(task)
    return _log_running


class LoggingMixin:
    """
    This mixin provides a quick way to log from classes within the Projects.
    It's mostly pasted from logging.LoggingAdaptor (which isn't available in < Py2.6),
    with a couple of compatibility tweaks.
    """
    root_logger_disabled = True
    log_prefix = None
    console = console

    _logger_name = None
    _logger = None

    @property
    def logger_name(self):
        """
        Returns the name of the log which will receive messages emitted
        by this object. This defaults to the class name (sanitized), but
        should almost always be overloaded by subclasses to make the
        hierarchy clear or by setting the `.name` attribute.

        eg. This would pick the Spider name (`.name`)
        """
        if not self._logger_name:
            name = getattr(self, 'name', None) or type(self).__name__.lower()
            self._logger_name = f"{name:<{PADDING_INTERNAL}}"
        return self._logger_name

    @property
    def logger(self):
        if not self._logger:
            # check the type of the output of _log_name, since logging.getLogger
            # doesn't bother, resulting in an obscure explosion for non-strings
            if not isinstance(self.logger_name, str):
                raise TypeError(
                    "%s.logger_name returned '%r' (%s). (wanted a string)" % (
                        type(self).__name__, self.logger_name, type(self.logger_name).__name__)
                )
            # configure the logger
            # scrapy discards the root handler and installs its own
            # https://gitlab1.cs.cityu.edu.hk/gsalter2/dockers/-/blob/37836f254c8fcc10f70b991eb0c6f5c31378bcb4/manim/manim/_config/logger_utils.py
            # FIXME: change scrapy's default handler to RichHandler
            self._logger = logging.getLogger(self.logger_name)
            self._logger.handlers = [RichHandler()]
            self._logger.propagate = not self.root_logger_disabled

            self._logger, _ = make_logger(self.logger_name)
        return self._logger

    def wrap_logger(self, level, msg, exc_info=False, *args, **kwargs):
        full_msg = NamespaceFormatter().format(
            # '%s >> ' % (self.log_prefix or self.logger_name) + msg,
            f"%-{PADDING_INTERNAL}s%s " % (self.log_prefix or self.logger_name, ">>") + msg,
            *args, **kwargs)

        # debug
        self.console.print(full_msg)

        return full_msg

    def log_debug(self, *args, **kwargs):
        """Logs a 'msg % args' with severity DEBUG."""
        return self.wrap_logger(logging.DEBUG, *args, **kwargs)

    def log_info(self, *args, **kwargs):
        """Logs a 'msg % args' with severity INFO."""
        return self.wrap_logger(logging.INFO, *args, **kwargs)

    def log_warning(self, *args, **kwargs):
        """Logs a 'msg % args' with severity WARNING."""
        return self.wrap_logger(logging.WARNING, *args, **kwargs)

    warn = log_warning

    def log_error(self, *args, **kwargs):
        """Logs a 'msg % args' with severity ERROR."""
        return self.wrap_logger(logging.ERROR, *args, **kwargs)

    def log_critical(self, *args, **kwargs):
        """Logs a 'msg % args' with severity CRITICAL."""
        return self.wrap_logger(logging.CRITICAL, *args, **kwargs)

    fatal = log_critical

    def log_exception(self, *args, **kwargs):
        """
        Log a 'msg % args' with severity ERROR, with the backtrace from
        the last exception raised.
        """

        # log the most recent exception
        kwargs['exc_info'] = True

        # the logger requires a message, so add a very dull one if none
        # was provided. (often, it's useful to just log the exception.)
        if not len(args):
            args = ("An exception occurred",)

        return self.log_error(*args, **kwargs)

    # backwards-compatibility
    log_last_exception = log_exception


# class LazyFormatter(string.Formatter):
#     """
#     Same as the default formatter, ie., <string>.format(*args, **kwargs)
#     but substitutes `{<key>}` for key present in <string>, but not supplied with args/kwargs.
#     """
#     def get_value(self, key, args, kwargs):
#         """Overrides string.Formatter.get_value"""
#         if isinstance(key, int):
#             return args[key]
#         else:
#             return kwargs.get(key, '{{{0}}}'.format(key))

class NamespaceFormatter(string.Formatter):
    """
    Provides defaults in case kw are not supplied by caller
    """

    def __init__(self, namespace={}):
        string.Formatter.__init__(self)
        self.namespace = namespace

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            try:
                # Check explicitly passed arguments first
                return kwargs[key]
            except KeyError:
                return self.namespace.get(key, '{{{0}}}'.format(key))
        else:
            string.Formatter.get_value(key, args, kwargs)


class TaskLoggerMixin(LoggingMixin):
    """
    Logs one dynamic message for a task
    - emojis
    """

    def log_task(self, level, status, log_msg: str or Callable, *args, **kwargs):
        if callable(log_msg):
            return self.wrap_logger(level, f"{status:{PADDING}}{log_msg(*args, **kwargs)}")
        return self.wrap_logger(level, f"{status:{PADDING}}{log_msg}", *args, **kwargs)

    def log_started(self, log_msg, *args, **kwargs):
        return self.log_task(logging.INFO, STARTED, log_msg, *args, **kwargs)

    def log_ok(self, log_msg, *args, **kwargs):
        return self.log_task(logging.INFO, OK, log_msg, *args, **kwargs)

    def log_failed(self, log_msg, exc: Exception, *args, **kwargs):
        self.log_task(logging.INFO, FAILED, log_msg, *args, **kwargs)
        if exc:
            # exclude '{' and '}' from the exception msg,
            # it causes and exception being raised by backing Formatter class.
            errmsg = reduce(lambda s, v: s.replace(v, ''), '{}', str(exc))
            self.log_task(logging.DEBUG, FAILED, errmsg)
        # TODO: not sure if/wt to return here

    def log_ended(self, log_msg, *args, **kwargs):
        return self.log_task(logging.INFO, DONE, log_msg, *args, **kwargs)

    def log_task_ended(self, log_msg, *args, **kwargs):
        self.console.rule(f"[bold blue] {TASK_ENDED}")
        msg = self.log_task(logging.INFO, DONE, log_msg, *args, **kwargs)
        self.console.rule()
        return msg


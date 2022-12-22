import configparser
import logging
import typing

from rich import color, errors, print as printf
from rich.console import Console
from rich.logging import RichHandler

from rich.theme import Theme

HIGHLIGHTED_KEYWORDS = [  # these keywords are highlighted specially
    "Played",
    "animations",
    "scene",
    "Reading",
    "Writing",
    "script",
    "arguments",
    "Invalid",
    "Aborting",
    "module",
    "File",
    "Rendering",
    "Rendered",
]
WRONG_COLOR_CONFIG_MSG = """
[logging.level.error]Your colour configuration couldn't be parsed.
Loading the default color configuration.[/logging.level.error]
"""

# throughout the codebase, use:
# >>> console.print() # instead of print()
# >>> with console.status()
# >>>    ...
console = Console(
    width=160,
    theme=Theme({
        "logging.keyword": 'bold yellow',
        # "logging.level.notset": 'dim',
        # "logging.level.debug": 'green',
        # "logging.level.info": 'green',
        # "logging.level.warning": 'red',
        # "logging.level.error": 'red bold',
        # "logging.level.critical": 'red bold reverse',
        # "log.level": None,
        # "log.time": 'cyan dim',
        # "log.message": None,
        # "log.path": 'dim',
        # "log.width": -1,
        # "log.height": -1,
        # "log.timestamps": True,
        # "repr.number": 'green'
    })
)


def parse_theme(parser: configparser.ConfigParser) -> Theme:
    """
    Configure the rich style of logger and console output.

    Parameters
    ----------
    parser : :class:`configparser.ConfigParser`
        A parser containing any .cfg files in use.

    Returns
    -------
    :class:`rich.Theme`
        The rich theme to be used by the manim logger.

    See Also
    --------
    :func:`make_logger`.

    """
    theme = {key.replace("_", "."): parser[key] for key in parser}

    theme["log.width"] = None if theme["log.width"] == "-1" else int(theme["log.width"])
    theme["log.height"] = (
        None if theme["log.height"] == "-1" else int(theme["log.height"])
    )
    theme["log.timestamps"] = False
    try:
        custom_theme = Theme(
            {
                k: v
                for k, v in theme.items()
                if k not in ["log.width", "log.height", "log.timestamps"]
            }
        )
    except (color.ColorParseError, errors.StyleSyntaxError):
        printf(WRONG_COLOR_CONFIG_MSG)
        custom_theme = None

    return custom_theme


def make_logger(name: str, verbosity: str = 'UNSET') \
        -> typing.Tuple[logging.Logger, Console]:
    """
    Make the manim logger and console.

    :param console:
    :param name:
    :param verbosity: The verbosity level of the logger.
    :param theme:

    """

    # set the rich handler
    RichHandler.KEYWORDS = HIGHLIGHTED_KEYWORDS
    rich_handler = RichHandler(
        rich_tracebacks=True, tracebacks_show_locals=True,
        console=console, show_time=True
    )

    # finally, the logger
    logger = logging.getLogger(name)
    logger.addHandler(rich_handler)
    logger.setLevel(verbosity)

    return logger, console

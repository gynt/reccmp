import argparse
import logging
import reccmp.color

# Threshold names accepted by --log-level, in increasing order of severity.
# CRITICAL is the quietest setting we offer: a message at that level reports
# that the tool cannot continue, so it is never worth hiding.
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

DEFAULT_LOG_LEVEL = logging.INFO


def preconfigure_logging():
    logging.addLevelName(
        logging.WARNING,
        f"{reccmp.color.Fore.YELLOW}{logging.getLevelName(logging.WARNING)}{reccmp.color.Style.RESET_ALL}",
    )
    logging.addLevelName(
        logging.ERROR,
        f"{reccmp.color.Fore.RED}{logging.getLevelName(logging.ERROR)}{reccmp.color.Style.RESET_ALL}",
    )
    logging.addLevelName(
        logging.CRITICAL,
        f"{reccmp.color.Fore.RED}{logging.getLevelName(logging.CRITICAL)}{reccmp.color.Style.RESET_ALL}",
    )


def argparse_add_logging_args(parser: argparse.ArgumentParser):
    parser.set_defaults(loglevel=DEFAULT_LOG_LEVEL)

    # Only one threshold can win, so let argparse reject a contradiction
    # instead of silently applying whichever option is declared last.
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--debug",
        action="store_const",
        const=logging.DEBUG,
        dest="loglevel",
        help="Print script debug information (same as --log-level debug)",
    )
    group.add_argument(
        "--quiet",
        "-q",
        action="store_const",
        const=logging.CRITICAL,
        dest="loglevel",
        help=(
            "Suppress progress, warning and error messages, keeping only the "
            "report on stdout (same as --log-level critical)"
        ),
    )
    group.add_argument(
        "--log-level",
        metavar="<level>",
        type=log_level,
        dest="loglevel",
        help="Lowest message severity to display: %s (default: info)"
        % ", ".join(LOG_LEVELS),
    )


def log_level(value: str) -> int:
    """Helper method for argparse, --log-level parameter"""
    try:
        return LOG_LEVELS[value.lower()]
    except KeyError:
        raise argparse.ArgumentTypeError(
            "invalid log level '%s' (choose from %s)" % (value, ", ".join(LOG_LEVELS))
        ) from None


def argparse_parse_logging(args: argparse.Namespace):
    if hasattr(args, "no_color"):
        reccmp.color.enable_color(not args.no_color)

    preconfigure_logging()
    logging.basicConfig(level=args.loglevel, format="[%(levelname)s] %(message)s")

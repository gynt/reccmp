"""Tests for the log verbosity options shared by every reccmp tool."""

import argparse
import logging
import pytest
from reccmp.project.logging import (
    DEFAULT_LOG_LEVEL,
    argparse_add_logging_args,
    log_level,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(allow_abbrev=False)
    argparse_add_logging_args(p)
    return p


def test_default_level():
    """Without any option, the threshold is unchanged from before these
    options existed."""
    assert parser().parse_args([]).loglevel == DEFAULT_LOG_LEVEL == logging.INFO


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--debug"], logging.DEBUG),
        (["--quiet"], logging.CRITICAL),
        (["-q"], logging.CRITICAL),
        (["--log-level", "debug"], logging.DEBUG),
        (["--log-level", "info"], logging.INFO),
        (["--log-level", "warning"], logging.WARNING),
        (["--log-level", "error"], logging.ERROR),
        (["--log-level", "critical"], logging.CRITICAL),
    ],
)
def test_level_options(argv: list[str], expected: int):
    assert parser().parse_args(argv).loglevel == expected


def test_log_level_is_case_insensitive():
    assert parser().parse_args(["--log-level", "WARNING"]).loglevel == logging.WARNING


def test_quiet_keeps_critical():
    """--quiet is the quietest setting, but a message saying we cannot continue
    still gets through."""
    assert parser().parse_args(["--quiet"]).loglevel <= logging.CRITICAL


@pytest.mark.parametrize(
    "argv",
    [
        ["--quiet", "--debug"],
        ["--debug", "--quiet"],
        ["--quiet", "--log-level", "debug"],
        ["--debug", "--log-level", "error"],
    ],
)
def test_conflicting_options_are_rejected(argv: list[str]):
    """Two thresholds at once is a mistake, not a silent last-one-wins."""
    with pytest.raises(SystemExit):
        parser().parse_args(argv)


def test_invalid_log_level_is_rejected():
    with pytest.raises(SystemExit):
        parser().parse_args(["--log-level", "shout"])

    with pytest.raises(argparse.ArgumentTypeError):
        log_level("shout")

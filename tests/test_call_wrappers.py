"""Tests for the CALL normalization used by projects that route calls to
original functions through a resolver/wrapper function."""

from unittest.mock import Mock
import pytest
from reccmp.cvdump.types import CvdumpTypesParser
from reccmp.compare.asm.call_wrappers import (
    ignore_call_targets,
    numbers_in_name,
    resolve_wrapped_calls,
)
from reccmp.compare.db import EntityDb
from reccmp.compare.event import ReccmpReportProtocol
from reccmp.compare.functions import CallComparisonOptions, FunctionComparator
from reccmp.compare.lines import LinesDb
from reccmp.types import EntityType, ImageId
from .raw_image import RawImage

# A name in the style used by a resolver template. The original address of the
# called function (0x1234000 == 19087360) is one of its template parameters.
WRAPPER_NAME = (
    "FunctionResolver::Resolver<void (__thiscall A::B::*)(int),0,19087360,"
    "&A::B::f,0>::GameFunction<void (__thiscall A::B::*)(int)>::"
    "CallHelper<void,void>::call"
)


@pytest.fixture(name="db")
def fixture_db() -> EntityDb:
    return EntityDb()


@pytest.fixture(name="lines_db")
def fixture_lines_db() -> LinesDb:
    return LinesDb()


@pytest.fixture(name="report")
def fixture_report_mock() -> ReccmpReportProtocol:
    return Mock(spec=ReccmpReportProtocol)


def test_numbers_in_name():
    """Only values that could plausibly be an address are candidates.
    Small template parameters (indices, flags) must be ignored."""
    assert list(numbers_in_name("Resolver<void,0,19087360,&f,0>")) == [19087360]
    assert list(numbers_in_name("0x1234000")) == [0x1234000]
    # Not a number on its own
    assert not list(numbers_in_name("PencilRenderCore12345678"))


def test_resolve_wrapped_calls():
    """The wrapper name embeds the orig address of the call target, so we use
    the text from the orig side for the recomp instruction."""
    recomp = [(0x500, "call " + WRAPPER_NAME), (0x505, "push 0")]
    assert resolve_wrapped_calls(recomp, {0x1234000: "<OFFSET12>"}) == [
        (0x500, "call <OFFSET12>"),
        (0x505, "push 0"),
    ]
    # Same, but the orig function is annotated so we have a real name for it
    assert resolve_wrapped_calls(recomp, {0x1234000: "A::B::f"}) == [
        (0x500, "call A::B::f"),
        (0x505, "push 0"),
    ]


def test_resolve_wrapped_calls_no_match():
    """A wrapper for some other function is still a mismatch."""
    recomp = [(0x500, "call " + WRAPPER_NAME)]
    assert resolve_wrapped_calls(recomp, {0x5555000: "<OFFSET12>"}) == recomp
    # No call targets in the orig function: nothing to resolve against
    assert resolve_wrapped_calls(recomp, {}) == recomp


def test_resolve_wrapped_calls_ignores_placeholder():
    """If we have no name for the recomp call target, there is nothing to read
    an original address from."""
    recomp = [(0x500, "call <OFFSET1>")]
    assert resolve_wrapped_calls(recomp, {0x1234000: "<OFFSET12>"}) == recomp


def test_ignore_call_targets():
    """Names and placeholders are replaced; registers are not."""
    excerpt = [
        (0x500, "call <OFFSET1>"),
        (0x505, "call MyFunc"),
        (0x50A, "call dword ptr [<OFFSET2>]"),
        (0x510, "call eax"),
        (0x512, "mov eax, <OFFSET1>"),
    ]
    assert ignore_call_targets(excerpt, {"<OFFSET1>", "<OFFSET2>", "MyFunc"}) == [
        (0x500, "call <CALL>"),
        (0x505, "call <CALL>"),
        (0x50A, "call dword ptr [<CALL>]"),
        (0x510, "call eax"),
        (0x512, "mov eax, <OFFSET1>"),
    ]


ORIG_BASE = 0x401000
RECOMP_BASE = 0x402000
# Both functions are `call rel32` (displacement 0) followed by `ret`,
# so the call target is the address right after the call instruction.
ORIG_CALL_TARGET = ORIG_BASE + 5
RECOMP_CALL_TARGET = RECOMP_BASE + 5

# Resolver instantiation for the function at ORIG_CALL_TARGET (0x401005).
ORIG_TARGET_WRAPPER_NAME = (
    "FunctionResolver::Resolver<void (__thiscall A::B::*)(int),0,"
    f"{ORIG_CALL_TARGET},&A::B::f,0>::CallHelper<void,void>::call"
)


def _compare_call(
    db: EntityDb,
    lines_db: LinesDb,
    report: ReccmpReportProtocol,
    call_options: CallComparisonOptions,
    recomp_target_name: str,
):
    """Compares two functions that each consist of a CALL and a RET.
    The orig call target is not annotated (so it gets a placeholder), while the
    recomp call target is the resolver instantiation `recomp_target_name`.
    """
    code = b"\xe8\x00\x00\x00\x00\xc3"

    with db.batch() as batch:
        batch.set(
            ImageId.ORIG,
            ORIG_BASE,
            type=EntityType.FUNCTION,
            name="test",
            size=len(code),
        )
        batch.set(
            ImageId.RECOMP,
            RECOMP_BASE,
            type=EntityType.FUNCTION,
            name="test",
            size=len(code),
        )
        batch.match(ORIG_BASE, RECOMP_BASE)

        batch.set(
            ImageId.RECOMP,
            RECOMP_CALL_TARGET,
            type=EntityType.FUNCTION,
            name=recomp_target_name,
            size=1,
        )

    orig_bin = RawImage.from_memory(code, base_addr=ORIG_BASE)
    recomp_bin = RawImage.from_memory(code, base_addr=RECOMP_BASE)

    comp = FunctionComparator(
        db,
        lines_db,
        orig_bin,
        recomp_bin,
        report,
        CvdumpTypesParser(),
        call_options=call_options,
    )
    (entity,) = list(db.get_functions())
    return comp.compare_function(entity)


def test_compare_function_wrapped_call_mismatch(
    db: EntityDb, lines_db: LinesDb, report: ReccmpReportProtocol
):
    """Without any option, the wrapper name does not match the orig call."""
    result = _compare_call(
        db, lines_db, report, CallComparisonOptions(), ORIG_TARGET_WRAPPER_NAME
    )
    assert result.match_ratio != 1.0


def test_compare_function_wrapped_call_resolved(
    db: EntityDb, lines_db: LinesDb, report: ReccmpReportProtocol
):
    """The wrapper name embeds the orig address of the call target, so the
    function is a 100% match with --resolve-wrapped-calls."""
    result = _compare_call(
        db,
        lines_db,
        report,
        CallComparisonOptions(resolve_wrapped_calls=True),
        ORIG_TARGET_WRAPPER_NAME,
    )
    assert result.match_ratio == 1.0


def test_compare_function_wrong_call_still_mismatches(
    db: EntityDb, lines_db: LinesDb, report: ReccmpReportProtocol
):
    """A wrapper for a different original function is a real mismatch and must
    still be reported with --resolve-wrapped-calls."""
    wrong_name = ORIG_TARGET_WRAPPER_NAME.replace(
        str(ORIG_CALL_TARGET), str(ORIG_CALL_TARGET + 0x100)
    )
    result = _compare_call(
        db,
        lines_db,
        report,
        CallComparisonOptions(resolve_wrapped_calls=True),
        wrong_name,
    )
    assert result.match_ratio != 1.0


def test_compare_function_ignore_call_targets(
    db: EntityDb, lines_db: LinesDb, report: ReccmpReportProtocol
):
    """With --ignore-call-targets, the call does not count towards the diff,
    whatever the target is."""
    result = _compare_call(
        db,
        lines_db,
        report,
        CallComparisonOptions(ignore_call_targets=True),
        "SomeUnrelatedFunction",
    )
    assert result.match_ratio == 1.0

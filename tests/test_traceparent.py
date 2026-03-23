import pathlib
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "plugins" / "trace" / "hooks" / "py"
sys.path.insert(0, str(HOOKS_DIR))

from traceparent import parse_traceparent


def test_parse_traceparent_accepts_valid_v00_header():
    parsed = parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")

    assert parsed == {
        "version": "00",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "parent_span_id": "00f067aa0ba902b7",
        "trace_flags": "01",
        "source": "external_traceparent",
    }


def test_parse_traceparent_accepts_future_version_with_suffix():
    parsed = parse_traceparent("02-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-05-deadbeef")

    assert parsed["version"] == "02"
    assert parsed["trace_flags"] == "05"


def test_parse_traceparent_rejects_invalid_inputs():
    assert parse_traceparent("") is None
    assert parse_traceparent("bogus") is None
    assert parse_traceparent("ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01") is None
    assert parse_traceparent("00-00000000000000000000000000000000-00f067aa0ba902b7-01") is None
    assert parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01") is None
    assert parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01-deadbeef") is None

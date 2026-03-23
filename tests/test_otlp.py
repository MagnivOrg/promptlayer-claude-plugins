import base64
import pathlib
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "plugins" / "trace" / "hooks" / "py"
sys.path.insert(0, str(HOOKS_DIR))

from otlp import SpanSpec, build_payload, build_span, parse_partial_success


def decode_b64(value: str) -> str:
    return base64.b64decode(value).hex()


def test_build_span_encodes_ids_and_attribute_types():
    span = build_span(
        SpanSpec(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            span_id="00f067aa0ba902b7",
            parent_span_id="89abcdef01234567",
            name="Claude Code session",
            kind="1",
            start_ns="100",
            end_ns="200",
            attrs={
                "string_attr": "value",
                "bool_attr": True,
                "int_attr": 42,
                "float_attr": 3.5,
                "obj_attr": {"k": "v"},
            },
        )
    )

    assert decode_b64(span["traceId"]) == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert decode_b64(span["spanId"]) == "00f067aa0ba902b7"
    assert decode_b64(span["parentSpanId"]) == "89abcdef01234567"
    assert span["kind"] == "SPAN_KIND_INTERNAL"

    attr_map = {item["key"]: item["value"] for item in span["attributes"]}
    assert attr_map["string_attr"] == {"stringValue": "value"}
    assert attr_map["bool_attr"] == {"boolValue": True}
    assert attr_map["int_attr"] == {"intValue": "42"}
    assert attr_map["float_attr"] == {"doubleValue": 3.5}
    assert attr_map["obj_attr"] == {"stringValue": '{"k":"v"}'}


def test_build_payload_wraps_spans_with_service_name():
    payload = build_payload([{"name": "span"}])

    assert payload["resourceSpans"][0]["resource"]["attributes"][0]["key"] == "service.name"
    assert payload["resourceSpans"][0]["scopeSpans"][0]["spans"] == [{"name": "span"}]


def test_parse_partial_success_handles_rejections_and_invalid_json():
    rejected, message = parse_partial_success('{"partialSuccess":{"rejectedSpans":2,"errorMessage":"bad span"}}')
    assert rejected == 2
    assert message == "bad span"

    rejected, message = parse_partial_success("not-json")
    assert rejected == 0
    assert message == ""

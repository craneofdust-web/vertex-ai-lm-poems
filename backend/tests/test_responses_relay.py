from __future__ import annotations

import json

from app.responses_relay import build_responses_payload, collect_stream_output, extract_json_object


def test_build_responses_payload_shape() -> None:
    payload = build_responses_payload(
        {
            "messages": [
                {"role": "system", "content": "rules"},
                {"role": "user", "content": "hello"},
            ]
        },
        model="gpt-5.3-codex",
        reasoning_effort="xhigh",
    )
    assert payload["model"] == "gpt-5.3-codex"
    assert payload["stream"] is True
    assert payload["input"][0]["content"][0]["type"] == "input_text"
    assert payload["reasoning"]["effort"] == "xhigh"


def test_collect_stream_output_and_extract_json() -> None:
    event_1 = json.dumps({"type": "response.output_text.delta", "delta": '{"target_id":"poem-1.md",'})
    event_2 = json.dumps(
        {
            "type": "response.output_text.delta",
            "delta": '"stance":"support","confidence":0.8,"what_works":["image"],"what_is_being_tested":[],"structural_gaps":[],"do_not_judge_harshly":["draft"],"anticipated_later_work":["later"],"rationale":"ok"}',
        }
    )
    lines = [
        f"data: {event_1}\n".encode(),
        f"data: {event_2}\n".encode(),
        b'data: [DONE]\n',
    ]
    text = collect_stream_output(lines)
    payload = extract_json_object(text)
    assert payload["target_id"] == "poem-1.md"
    assert payload["stance"] == "support"


def test_extract_json_object_repairs_smart_quotes() -> None:
    raw = '{"target_id":"poem-2.md","stance":"qualified_positive","rationale":"works。”}'
    payload = extract_json_object(raw)
    assert payload["target_id"] == "poem-2.md"
    assert payload["stance"] == "qualified_positive"

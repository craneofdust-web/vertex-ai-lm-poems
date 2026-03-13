from __future__ import annotations

import json
import ssl
import time
from pathlib import Path
from typing import Any, Iterable
from urllib import error as urlerror, request

import certifi


JSON_REPAIR_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "‘": "'",
        "’": "'",
    }
)


def _json_repair_candidates(raw: str) -> list[str]:
    candidates = [str(raw or "").strip()]
    repaired = candidates[0].translate(JSON_REPAIR_TRANSLATION).replace("\ufeff", "").strip()
    if repaired and repaired not in candidates:
        candidates.append(repaired)
    return candidates


def build_responses_input(messages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user").strip() or "user"
        content = str(message.get("content") or "").strip()
        out.append(
            {
                "role": role,
                "content": [{"type": "input_text", "text": content}],
            }
        )
    return out


def build_responses_payload(
    prompt_job: dict[str, Any],
    model: str,
    reasoning_effort: str = "xhigh",
) -> dict[str, Any]:
    return {
        "model": model,
        "stream": True,
        "input": build_responses_input(prompt_job.get("messages", [])),
        "reasoning": {"effort": reasoning_effort},
    }


def extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty response text")
    if raw.startswith("```"):
        parts = raw.split("```")
        fenced = "\n".join(part for part in parts if part and not part.startswith("json"))
        raw = fenced.strip() or raw
    for candidate in _json_repair_candidates(raw):
        start = candidate.find("{")
        if start < 0:
            continue
        decoder = json.JSONDecoder()
        positions = [index for index, char in enumerate(candidate) if char == "{"]
        for index in positions:
            try:
                payload, _ = decoder.raw_decode(candidate, index)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        end = candidate.rfind("}")
        if end >= start:
            try:
                payload = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
    raise ValueError("no valid JSON object found in response text")


def text_from_response_payload(payload: dict[str, Any]) -> str:
    response_payload = payload.get("response")
    response = response_payload if isinstance(response_payload, dict) else payload
    output = response.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "output_text":
                    parts.append(str(block.get("text") or ""))
        return "".join(parts).strip()
    text = response.get("output_text")
    return str(text or "").strip()


def collect_stream_output(lines: Iterable[bytes | str]) -> str:
    deltas: list[str] = []
    completed_payloads: list[dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, bytes) else str(raw_line)
        stripped = line.strip()
        if not stripped or not stripped.startswith("data:"):
            continue
        data = stripped[5:].strip()
        if data == "[DONE]":
            break
        payload = json.loads(data)
        if not isinstance(payload, dict):
            continue
        event_type = str(payload.get("type") or "")
        if event_type.endswith("output_text.delta") or event_type.endswith("output_text.annotation.added"):
            delta = payload.get("delta")
            if isinstance(delta, str):
                deltas.append(delta)
            continue
        if event_type.endswith("completed"):
            completed_payloads.append(payload)
            continue
        delta = payload.get("delta")
        if isinstance(delta, str):
            deltas.append(delta)
    text = "".join(deltas).strip()
    if text:
        return text
    for payload in reversed(completed_payloads):
        extracted = text_from_response_payload(payload)
        if extracted:
            return extracted
    raise ValueError("no output text recovered from streamed response")


def post_responses_stream(
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: float = 180.0,
    max_attempts: int = 6,
    stop_on_status: Iterable[int] | None = None,
) -> str:
    normalized_base = base_url.rstrip("/")
    endpoint = normalized_base if normalized_base.endswith("/responses") else f"{normalized_base}/responses"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "text/event-stream",
            "User-Agent": "vertex-poems-relay-runner/0.1",
        },
        method="POST",
    )
    max_attempts = max(1, int(max_attempts))
    stop_on = {int(code) for code in (stop_on_status or [])}
    for attempt in range(1, max_attempts + 1):
        try:
            with request.urlopen(req, timeout=timeout, context=ssl_context) as response:
                return collect_stream_output(response)
        except urlerror.HTTPError as exc:
            status = int(getattr(exc, "code", 0) or 0)
            if status in stop_on:
                raise
            retryable = status == 429 or 500 <= status < 600
            if not retryable or attempt >= max_attempts:
                raise
            retry_after = ""
            if exc.headers:
                retry_after = str(exc.headers.get("Retry-After") or "").strip()
            delay = 15 * (2 ** (attempt - 1))
            if retry_after.isdigit():
                delay = max(delay, int(retry_after))
            time.sleep(min(delay, 300))
    raise ValueError("responses relay exhausted retry attempts")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

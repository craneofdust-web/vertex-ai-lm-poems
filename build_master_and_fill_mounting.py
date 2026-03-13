import argparse
import glob
import hashlib
import json
import math
import os
import random
import re
import shutil
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import vertexai
from google.api_core import exceptions as gcp_exceptions
from vertexai.generative_models import GenerativeModel


DEFAULT_PROJECT_ID = "your-gcp-project-id"
DEFAULT_LOCATION = "us-central1"
DEFAULT_MODEL_CANDIDATES = ["gemini-3.1", "gemini-3-pro", "gemini-2.5-pro"]
DEFAULT_SOURCE_FOLDER = "./sample_poems"
DEFAULT_EXCLUDE_DIRS = {".obsidian", ".trash", "Templates"}
EXTRA_FRAGMENT_PATHS = os.getenv("EXTRA_FRAGMENT_PATHS", "")

FILL_TEMPERATURE = float(os.getenv("FILL_TEMPERATURE", "0.12"))
FILL_MAX_RETRIES = int(os.getenv("FILL_MAX_RETRIES", "3"))
FILL_BASE_RETRY_SECONDS = int(os.getenv("FILL_BASE_RETRY_SECONDS", "2"))
FILL_TOP_K = int(os.getenv("FILL_TOP_K", "3"))
FILL_BATCH_SIZE = int(os.getenv("FILL_BATCH_SIZE", "8"))
FILL_MAX_POEM_CHARS = int(os.getenv("FILL_MAX_POEM_CHARS", "1800"))
ALLOW_HEURISTIC_FALLBACK = os.getenv("ALLOW_HEURISTIC_FALLBACK", "1") == "1"
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

TIER_ORDER = {
    "?箇?憭抵釵": 0,
    "撖阡???": 1,
    "?脤?頧": 2,
    "蝯扔憟抒儔": 3,
}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def canonicalize_text(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE).lower()


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def clip_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.75)]
    tail = text[-int(max_chars * 0.25) :]
    return f"{head}\n...\n{tail}"


def parse_json_response(raw_text: str) -> Any:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def quote_in_source(quote: str, source_content: str) -> bool:
    if quote in source_content:
        return True
    if normalize_whitespace(quote) in normalize_whitespace(source_content):
        return True
    q = canonicalize_text(quote)
    s = canonicalize_text(source_content)
    return bool(q) and q in s


def repair_quote(quote: str, source_content: str) -> str | None:
    q = quote.strip().strip("\"'`“”‘’")
    if not q:
        return None
    if quote_in_source(q, source_content):
        return q
    lines = [line.strip() for line in source_content.splitlines() if line.strip()]
    if not lines:
        return None
    segments = [seg.strip() for seg in re.split(r"(?:\.{3,}|??)", q) if seg.strip()]
    if segments:
        seg_norm = [canonicalize_text(seg) for seg in segments if canonicalize_text(seg)]
        for line in lines:
            ln = canonicalize_text(line)
            if ln and all(seg in ln for seg in seg_norm):
                return line
    qn = canonicalize_text(q)
    best = ""
    best_score = 0.0
    for line in lines:
        ln = canonicalize_text(line)
        if not ln:
            continue
        score = SequenceMatcher(None, qn, ln).ratio()
        if score > best_score:
            best_score = score
            best = line
    return best if best_score >= 0.72 else None


def choose_quote_from_poem(poem_content: str) -> str:
    for line in poem_content.splitlines():
        line = line.strip()
        if len(line) >= 8:
            return line
    return poem_content.strip()[:60]


def normalize_node_id(node_id: str, node_name: str) -> str:
    base = (node_id or "").strip().lower()
    base = re.sub(r"[^a-z0-9_]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    if base:
        return base
    fallback = canonicalize_text(node_name)
    if fallback:
        return f"node_{fallback[:30]}"
    h = hashlib.sha1(node_name.encode("utf-8")).hexdigest()[:10]
    return f"node_{h}"


def choose_counter_value(counter: Counter, fallback: str = "") -> str:
    return counter.most_common(1)[0][0] if counter else fallback


def choose_longest(values: Iterable[str], fallback: str = "") -> str:
    values = [v for v in values if v]
    return max(values, key=len) if values else fallback


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        while True:
            chunk = file_obj.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def scan_markdown_poems(folder_path: Path, exclude_dirs: set[str]) -> List[Dict[str, str]]:
    poems: List[Dict[str, str]] = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
        current_folder = os.path.basename(root)
        for filename in files:
            if not filename.endswith(".md"):
                continue
            file_path = Path(root) / filename
            rel = str(file_path.relative_to(folder_path)).replace("\\", "/")
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            poems.append({"id": rel, "filename": filename, "folder": current_folder, "content": content})
    return poems


def load_fragments(pattern: str) -> List[Tuple[str, List[Dict[str, Any]]]]:
    out: List[Tuple[str, List[Dict[str, Any]]]] = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                out.append((path, data))
        except Exception:
            continue
    return out


def load_fragments_from_patterns(patterns: List[str]) -> List[Tuple[str, List[Dict[str, Any]]]]:
    merged: Dict[str, List[Dict[str, Any]]] = {}
    for pattern in patterns:
        for path, data in load_fragments(pattern):
            merged[path] = data
    return sorted(merged.items(), key=lambda item: item[0])


@dataclass
class MergeBucket:
    node_id: str
    id_variants: Counter
    name_variants: Counter
    tier_variants: Counter
    unlock_values: List[str]
    description_values: List[str]
    prereq_set: set[str]
    citations: Dict[Tuple[str, str], Dict[str, str]]
    source_fragments: set[str]
    support_count: int


def merge_fragments_to_master(fragments: List[Tuple[str, List[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, MergeBucket] = {}
    for fragment_file, nodes in fragments:
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_name = str(node.get("node_name", "")).strip()
            node_id = normalize_node_id(str(node.get("node_id", "")).strip(), node_name)
            bucket = buckets.get(node_id)
            if bucket is None:
                bucket = MergeBucket(
                    node_id=node_id,
                    id_variants=Counter(),
                    name_variants=Counter(),
                    tier_variants=Counter(),
                    unlock_values=[],
                    description_values=[],
                    prereq_set=set(),
                    citations={},
                    source_fragments=set(),
                    support_count=0,
                )
                buckets[node_id] = bucket
            raw_id = str(node.get("node_id", "")).strip()
            tier = str(node.get("node_tier", "")).strip()
            unlock = str(node.get("unlock_condition", "")).strip()
            desc = str(node.get("description", "")).strip()
            if raw_id:
                bucket.id_variants[raw_id] += 1
            if node_name:
                bucket.name_variants[node_name] += 1
            if tier:
                bucket.tier_variants[tier] += 1
            if unlock:
                bucket.unlock_values.append(unlock)
            if desc:
                bucket.description_values.append(desc)
            prereq = node.get("prerequisite_nodes", [])
            if isinstance(prereq, list):
                for p in prereq:
                    p = str(p).strip()
                    if p:
                        bucket.prereq_set.add(p)
            citations = node.get("citations", [])
            if isinstance(citations, list):
                for c in citations:
                    if not isinstance(c, dict):
                        continue
                    source_id = str(c.get("source_id", "")).strip()
                    quote = str(c.get("quote", "")).strip()
                    if not source_id or not quote:
                        continue
                    key = (source_id, canonicalize_text(quote))
                    existing = bucket.citations.get(key)
                    item = {
                        "source_id": source_id,
                        "source_title": str(c.get("source_title", "")).strip(),
                        "folder_status": str(c.get("folder_status", "")).strip(),
                        "quote": quote,
                        "why": str(c.get("why", "")).strip(),
                    }
                    if existing is None:
                        bucket.citations[key] = item
                    else:
                        if len(item["why"]) > len(existing.get("why", "")):
                            existing["why"] = item["why"]
                        if len(item["quote"]) > len(existing.get("quote", "")):
                            existing["quote"] = item["quote"]
                        if not existing.get("source_title") and item["source_title"]:
                            existing["source_title"] = item["source_title"]
                        if not existing.get("folder_status") and item["folder_status"]:
                            existing["folder_status"] = item["folder_status"]
            bucket.source_fragments.add(fragment_file)
            bucket.support_count += 1

    node_ids = set(buckets.keys())
    master_nodes: List[Dict[str, Any]] = []
    for node_id, bucket in buckets.items():
        prereq = sorted({p for p in bucket.prereq_set if p and p != node_id and p in node_ids})
        unresolved = sorted({p for p in bucket.prereq_set if p and p != node_id and p not in node_ids})
        master_nodes.append(
            {
                "node_id": node_id,
                "node_name": choose_counter_value(bucket.name_variants, fallback=node_id),
                "node_tier": choose_counter_value(bucket.tier_variants, fallback="?脤?頧"),
                "prerequisite_nodes": prereq,
                "unlock_condition": choose_longest(bucket.unlock_values, fallback=""),
                "description": choose_longest(bucket.description_values, fallback=""),
                "citations": sorted(bucket.citations.values(), key=lambda x: (x.get("source_id", ""), x.get("quote", ""))),
                "metadata": {
                    "support_count": bucket.support_count,
                    "source_fragments": sorted(bucket.source_fragments),
                    "node_id_variants": [{"value": k, "count": v} for k, v in bucket.id_variants.most_common()],
                    "node_name_variants": [{"value": k, "count": v} for k, v in bucket.name_variants.most_common()],
                    "unresolved_prerequisite_nodes": unresolved,
                },
            }
        )
    master_nodes.sort(
        key=lambda n: (
            TIER_ORDER.get(str(n.get("node_tier", "")).strip(), 99),
            -int(n.get("metadata", {}).get("support_count", 0)),
            str(n.get("node_name", "")),
        )
    )
    return master_nodes


def write_master_markdown(master_nodes: List[Dict[str, Any]], output_path: Path) -> None:
    lines = ["# Master Skill Web", "", f"- total_nodes: {len(master_nodes)}", ""]
    for idx, node in enumerate(master_nodes, start=1):
        meta = node.get("metadata", {})
        lines.append(f"## {idx}. {node.get('node_name', '')} (`{node.get('node_id', '')}`)")
        lines.append(f"- tier: {node.get('node_tier', '')}")
        lines.append(f"- support_count: {meta.get('support_count', 0)}")
        prereq = node.get("prerequisite_nodes", [])
        lines.append(f"- prerequisite_nodes: {', '.join(prereq) if prereq else '(none)'}")
        lines.append(f"- unlock_condition: {node.get('unlock_condition', '')}")
        lines.append(f"- description: {node.get('description', '')}")
        citations = node.get("citations", [])
        lines.append(f"- citations: {len(citations)}")
        for c in citations[:4]:
            lines.append(f"  - `{c.get('source_id', '')}` \"{normalize_whitespace(c.get('quote', ''))}\"")
        if len(citations) > 4:
            lines.append(f"  - ... ({len(citations) - 4} more)")
        lines.append("")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def init_mounting_records(poems: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    return {
        poem["id"]: {
            "source_id": poem["id"],
            "source_title": poem["filename"],
            "folder_status": poem["folder"],
            "matched_nodes": [],
            "match_count": 0,
        }
        for poem in poems
    }


def dedupe_and_sort_matches(record: Dict[str, Any]) -> None:
    deduped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for item in record.get("matched_nodes", []):
        key = (
            str(item.get("node_id", "")),
            str(item.get("evidence_type", "")),
            canonicalize_text(str(item.get("quote", ""))),
        )
        existing = deduped.get(key)
        if existing is None or float(item.get("confidence", 0.0)) > float(existing.get("confidence", 0.0)):
            deduped[key] = item
    matches = list(deduped.values())
    matches.sort(
        key=lambda m: (
            TIER_ORDER.get(str(m.get("node_tier", "")).strip(), 99),
            -float(m.get("confidence", 0.0)),
            str(m.get("node_name", "")),
        )
    )
    record["matched_nodes"] = matches
    record["match_count"] = len(matches)


def build_seed_mounting(poems: List[Dict[str, str]], master_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records = init_mounting_records(poems)
    for node in master_nodes:
        for c in node.get("citations", []):
            source_id = str(c.get("source_id", ""))
            if source_id not in records:
                continue
            records[source_id]["matched_nodes"].append(
                {
                    "node_id": str(node.get("node_id", "")),
                    "node_name": str(node.get("node_name", "")),
                    "node_tier": str(node.get("node_tier", "")),
                    "quote": str(c.get("quote", "")),
                    "why": str(c.get("why", "")),
                    "confidence": 1.0,
                    "evidence_type": "master_citation",
                    "source": "master_skill_web",
                }
            )
    for record in records.values():
        dedupe_and_sort_matches(record)
    return sorted(records.values(), key=lambda x: x["source_id"])


def select_model(candidates: List[str], project_id: str, location: str) -> Tuple[str, GenerativeModel]:
    print(f"[info] init Vertex AI project={project_id} location={location}")
    vertexai.init(project=project_id, location=location)
    last_error: Exception | None = None
    for model_name in candidates:
        try:
            model = GenerativeModel(model_name)
            model.generate_content(
                "[]",
                generation_config={"response_mime_type": "application/json", "temperature": 0.0},
            )
            print(f"[info] selected model: {model_name}")
            return model_name, model
        except Exception as error:
            last_error = error
            print(f"[warn] model unavailable: {model_name} ({type(error).__name__})")
    raise RuntimeError(f"no available model from candidates={candidates}, last_error={last_error}")


def build_node_catalog_for_prompt(master_nodes: List[Dict[str, Any]]) -> str:
    lines = []
    for node in master_nodes:
        desc = normalize_whitespace(str(node.get("description", "")))[:120]
        lines.append(
            f"- {node.get('node_id', '')} | {node.get('node_tier', '')} | "
            f"{node.get('node_name', '')} | {desc}"
        )
    return "\n".join(lines)


def build_fill_prompt(catalog_text: str, poems_payload: List[Dict[str, str]], top_k: int) -> str:
    payload_text = json.dumps(poems_payload, ensure_ascii=False, indent=2)
    return f"""
You are a strict poetry classification engine.

Task:
Assign each poem to up to {top_k} suitable nodes from catalog.

Rules:
1) Use only node_id from catalog.
2) quote must be an exact contiguous substring from poem_text.
3) why is concise (1-2 sentences).
4) Return JSON array only.

Node catalog:
{catalog_text}

Poems (JSON):
{payload_text}

Output:
[
  {{
    "source_id": "id",
    "matches": [
      {{"node_id":"...", "quote":"...", "why":"...", "confidence":0.0}}
    ]
  }}
]
""".strip()


def validate_fill_items(
    items: Any,
    batch_poems: Dict[str, Dict[str, str]],
    master_nodes_by_id: Dict[str, Dict[str, Any]],
    top_k: int,
) -> Dict[str, List[Dict[str, Any]]]:
    output: Dict[str, List[Dict[str, Any]]] = {source_id: [] for source_id in batch_poems}
    if not isinstance(items, list):
        return output
    for item in items:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id", "")).strip()
        if source_id not in batch_poems:
            continue
        matches = item.get("matches", [])
        if not isinstance(matches, list):
            continue
        candidate_matches: List[Dict[str, Any]] = []
        for match in matches:
            if not isinstance(match, dict):
                continue
            node_id = str(match.get("node_id", "")).strip()
            if node_id not in master_nodes_by_id:
                continue
            quote = str(match.get("quote", "")).strip()
            repaired = repair_quote(quote, batch_poems[source_id]["content"])
            if repaired is None:
                continue
            why = str(match.get("why", "")).strip() or "model assigned this node by stylistic signals"
            try:
                confidence = float(match.get("confidence", 0.0))
            except Exception:
                confidence = 0.0
            confidence = max(0.0, min(confidence, 1.0))
            candidate_matches.append(
                {
                    "node_id": node_id,
                    "node_name": master_nodes_by_id[node_id]["node_name"],
                    "node_tier": master_nodes_by_id[node_id]["node_tier"],
                    "quote": repaired,
                    "why": why,
                    "confidence": confidence,
                    "evidence_type": "model_fill",
                    "source": "vertex_fill",
                }
            )
        deduped: Dict[str, Dict[str, Any]] = {}
        for m in candidate_matches:
            old = deduped.get(m["node_id"])
            if old is None or m["confidence"] > old["confidence"]:
                deduped[m["node_id"]] = m
        output[source_id] = sorted(
            deduped.values(),
            key=lambda m: (TIER_ORDER.get(m["node_tier"], 99), -m["confidence"], m["node_name"]),
        )[:top_k]
    return output


def tier_bias_score(folder_status: str, node_tier: str) -> float:
    status = folder_status or ""
    status_lower = status.lower()
    if "draft" in status_lower:
        return 0.20 if node_tier == "初級底層" else 0.0
    if "in_progress" in status_lower or "unfinished" in status_lower:
        return 0.20 if node_tier == "中階技法" else 0.0
    return 0.15 if node_tier in {"高階表達", "元能力與系統"} else 0.0


def heuristic_assign(poem: Dict[str, str], master_nodes: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    poem_norm = canonicalize_text(poem["content"])[:1200]
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for node in master_nodes:
        node_norm = canonicalize_text(f"{node.get('node_name', '')} {node.get('description', '')}")[:500]
        if not node_norm:
            continue
        score = SequenceMatcher(None, poem_norm, node_norm).ratio() + tier_bias_score(poem.get("folder", ""), str(node.get("node_tier", "")))
        scored.append((score, node))
    scored.sort(key=lambda x: x[0], reverse=True)
    quote = choose_quote_from_poem(poem["content"])
    out: List[Dict[str, Any]] = []
    for score, node in scored[:top_k]:
        out.append(
            {
                "node_id": str(node.get("node_id", "")),
                "node_name": str(node.get("node_name", "")),
                "node_tier": str(node.get("node_tier", "")),
                "quote": quote,
                "why": "heuristic fallback based on textual similarity and folder status",
                "confidence": round(max(0.1, min(0.45, score)), 3),
                "evidence_type": "heuristic_fallback",
                "source": "local_heuristic",
            }
        )
    return out


def request_fill_batch(
    model: GenerativeModel,
    catalog_text: str,
    batch_poems: Dict[str, Dict[str, str]],
    master_nodes_by_id: Dict[str, Dict[str, Any]],
    top_k: int,
) -> Dict[str, List[Dict[str, Any]]]:
    payload = [
        {
            "source_id": poem["id"],
            "source_title": poem["filename"],
            "folder_status": poem["folder"],
            "poem_text": clip_text(poem["content"], FILL_MAX_POEM_CHARS),
        }
        for poem in batch_poems.values()
    ]
    prompt = build_fill_prompt(catalog_text, payload, top_k)
    last_error: Exception | None = None
    for attempt in range(1, FILL_MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json", "temperature": FILL_TEMPERATURE},
            )
            parsed = parse_json_response(response.text)
            return validate_fill_items(parsed, batch_poems, master_nodes_by_id, top_k)
        except (
            gcp_exceptions.ResourceExhausted,
            gcp_exceptions.ServiceUnavailable,
            gcp_exceptions.DeadlineExceeded,
        ) as error:
            last_error = error
            if attempt == FILL_MAX_RETRIES:
                break
            sleep_seconds = FILL_BASE_RETRY_SECONDS * (2 ** (attempt - 1))
            print(f"[warn] fill API temporary failure, retry in {sleep_seconds}s ({attempt}/{FILL_MAX_RETRIES})")
            time.sleep(sleep_seconds)
        except (json.JSONDecodeError, ValueError, gcp_exceptions.InvalidArgument) as error:
            last_error = error
            if attempt == FILL_MAX_RETRIES:
                break
            print(f"[warn] fill response format issue, retry ({attempt}/{FILL_MAX_RETRIES})")
        except Exception as error:
            last_error = error
            if attempt == FILL_MAX_RETRIES:
                break
            print(f"[warn] fill unknown issue, retry ({attempt}/{FILL_MAX_RETRIES})")
    assert last_error is not None
    raise last_error


def mount_fill_results(records: Dict[str, Dict[str, Any]], fill_assignments: Dict[str, List[Dict[str, Any]]]) -> None:
    for source_id, matches in fill_assignments.items():
        if source_id not in records:
            continue
        records[source_id]["matched_nodes"].extend(matches)
        dedupe_and_sort_matches(records[source_id])


def write_mounting_markdown(records: List[Dict[str, Any]], output_path: Path) -> None:
    lines: List[str] = ["# Poem Mounting Full Index", ""]
    footnotes: List[str] = []
    footnote_idx = 1
    for record in records:
        lines.append(f"## {record['source_title']}")
        lines.append(f"- source_id: `{record['source_id']}`")
        lines.append(f"- folder_status: {record['folder_status']}")
        lines.append(f"- match_count: {record.get('match_count', 0)}")
        matches = record.get("matched_nodes", [])
        if not matches:
            lines.append("- matched_nodes: (none)")
            lines.append("")
            continue
        for m in matches[:6]:
            ref = f"[^{footnote_idx}]"
            lines.append(
                f"- [{m.get('evidence_type', '')}] {m.get('node_tier', '')} "
                f"{m.get('node_name', '')} (`{m.get('node_id', '')}`) "
                f"conf={m.get('confidence', 0.0):.3f} {ref}"
            )
            quote = normalize_whitespace(str(m.get("quote", "")))
            why = normalize_whitespace(str(m.get("why", "")))
            source = str(m.get("source", ""))
            footnotes.append(f"[^{footnote_idx}]: source={source}; quote=\"{quote}\"; why={why}")
            footnote_idx += 1
        if len(matches) > 6:
            lines.append(f"- ... ({len(matches) - 6} more)")
        lines.append("")
    if footnotes:
        lines.append("---")
        lines.append("")
        lines.extend(footnotes)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def snapshot_inputs(workdir: Path, run_dir: Path) -> Dict[str, Any]:
    snapshot_dir = run_dir / "snapshot"
    ensure_dir(snapshot_dir)
    patterns = [
        "brainstorm_skill_webs.py",
        "poem_mounting_index.json",
        "poem_mounting_index.md",
        "skill_web_fragment_*.json",
        "skill_web_fragment_*.md",
        "archives/skill_web_fragments_*/skill_web_fragment_*.json",
        "archives/skill_web_fragments_*/skill_web_fragment_*.md",
        "閰拇?憭雁摨行??賜雯 (Poetry Skill Web) ??蝑.txt",
    ]
    copied: List[Dict[str, Any]] = []
    for pattern in patterns:
        for file_name in sorted(glob.glob(pattern)):
            src = workdir / file_name
            dst = snapshot_dir / src.name
            try:
                shutil.copy2(src, dst)
                copied.append({"name": src.name, "size": src.stat().st_size, "sha256": sha256_file(dst)})
            except Exception:
                continue
    manifest = {"snapshot_dir": str(snapshot_dir), "files": copied}
    (run_dir / "snapshot_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def print_stats(label: str, records: List[Dict[str, Any]]) -> None:
    counts = [int(r.get("match_count", 0)) for r in records]
    if not counts:
        print(f"[info] {label}: no records")
        return
    total = len(counts)
    with_match = sum(1 for c in counts if c > 0)
    print(
        f"[info] {label}: total={total}, with_match={with_match}, "
        f"avg={sum(counts)/total:.2f}, max={max(counts)}, min={min(counts)}"
    )


def run(args: argparse.Namespace) -> None:
    random.seed(RANDOM_SEED)
    workdir = Path(args.workdir).resolve()
    run_label = args.run_label or f"run_{now_stamp()}"
    run_dir = workdir / "runs" / run_label
    ensure_dir(run_dir)
    print(f"[info] run_dir={run_dir}")
    snapshot_info = snapshot_inputs(workdir, run_dir)
    print(f"[info] snapshot files={len(snapshot_info['files'])}")

    fragment_patterns = [
        str(workdir / "skill_web_fragment_*.json"),
        str(workdir / "archives" / "skill_web_fragments_*" / "skill_web_fragment_*.json"),
    ]
    extra_paths = [p.strip() for p in EXTRA_FRAGMENT_PATHS.split(",") if p.strip()]
    fragment_patterns.extend(extra_paths)
    fragments = load_fragments_from_patterns(fragment_patterns)
    if not fragments:
        raise RuntimeError("no skill_web_fragment_*.json found")
    print(f"[info] loaded fragments={len(fragments)}")
    master_nodes = merge_fragments_to_master(fragments)
    print(f"[info] merged master nodes={len(master_nodes)}")
    (run_dir / "master_skill_web.json").write_text(json.dumps(master_nodes, ensure_ascii=False, indent=2), encoding="utf-8")
    write_master_markdown(master_nodes, run_dir / "master_skill_web.md")

    poems = scan_markdown_poems(Path(args.source_folder), DEFAULT_EXCLUDE_DIRS)
    poems_by_id = {p["id"]: p for p in poems}
    print(f"[info] scanned poems={len(poems)}")

    seed_records = build_seed_mounting(poems, master_nodes)
    print_stats("seed_mounting", seed_records)
    (run_dir / "poem_mounting_seed.json").write_text(json.dumps(seed_records, ensure_ascii=False, indent=2), encoding="utf-8")

    seed_unmatched_all = [r["source_id"] for r in seed_records if r.get("match_count", 0) == 0]
    unmatched_ids = list(seed_unmatched_all)
    if args.max_unmatched > 0:
        unmatched_ids = unmatched_ids[: args.max_unmatched]
    (run_dir / "unmatched_poems_before_fill.json").write_text(json.dumps(unmatched_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[info] unmatched before fill={len(unmatched_ids)}")

    records_map = {
        r["source_id"]: {
            **r,
            "matched_nodes": list(r.get("matched_nodes", [])),
            "match_count": int(r.get("match_count", 0)),
        }
        for r in seed_records
    }
    fill_records: List[Dict[str, Any]] = []

    if not args.skip_fill and unmatched_ids:
        candidates = [m.strip() for m in args.model_candidates.split(",") if m.strip()]
        _, model = select_model(candidates, args.project_id, args.location)
        master_nodes_by_id = {n["node_id"]: n for n in master_nodes}
        catalog_text = build_node_catalog_for_prompt(master_nodes)
        batches = [unmatched_ids[i : i + args.fill_batch_size] for i in range(0, len(unmatched_ids), args.fill_batch_size)]
        total_batches = len(batches)
        fill_start = time.time()
        for idx, batch_ids in enumerate(batches, start=1):
            batch_poems = {pid: poems_by_id[pid] for pid in batch_ids if pid in poems_by_id}
            print(f"[info] fill batch {idx}/{total_batches}, poems={len(batch_poems)}")
            try:
                batch_assign = request_fill_batch(model, catalog_text, batch_poems, master_nodes_by_id, args.fill_top_k)
            except Exception as error:
                print(f"[warn] fill batch failed: {error}")
                batch_assign = {pid: [] for pid in batch_poems}
            if ALLOW_HEURISTIC_FALLBACK:
                for pid in batch_poems:
                    if not batch_assign.get(pid):
                        batch_assign[pid] = heuristic_assign(batch_poems[pid], master_nodes, args.fill_top_k)
            mount_fill_results(records_map, batch_assign)
            for pid, matches in batch_assign.items():
                fill_records.append({"source_id": pid, "match_count": len(matches), "matches": matches})
            elapsed = time.time() - fill_start
            avg_batch = elapsed / idx
            remain_seconds = avg_batch * (total_batches - idx)
            eta = datetime.fromtimestamp(datetime.now().timestamp() + remain_seconds).strftime("%Y-%m-%d %H:%M")
            print(f"[info] fill progress={idx}/{total_batches}, remaining~{math.ceil(remain_seconds/60)}m, eta={eta}")

    final_records = sorted(records_map.values(), key=lambda x: x["source_id"])
    for r in final_records:
        dedupe_and_sort_matches(r)
    print_stats("final_mounting", final_records)

    (run_dir / "fill_assignments.json").write_text(json.dumps(fill_records, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "poem_mounting_full.json").write_text(json.dumps(final_records, ensure_ascii=False, indent=2), encoding="utf-8")
    write_mounting_markdown(final_records, run_dir / "poem_mounting_full.md")

    meta = {
        "run_label": run_label,
        "run_dir": str(run_dir),
        "source_folder": args.source_folder,
        "fragments": len(fragments),
        "master_nodes": len(master_nodes),
        "poems_total": len(poems),
        "seed_unmatched": len(seed_unmatched_all),
        "final_unmatched": len([r for r in final_records if r.get("match_count", 0) == 0]),
        "skip_fill": args.skip_fill,
        "fill_top_k": args.fill_top_k,
        "fill_batch_size": args.fill_batch_size,
        "allow_heuristic_fallback": ALLOW_HEURISTIC_FALLBACK,
    }
    (run_dir / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[info] completed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build master skill web and fill unmatched poem mounting without touching original files."
    )
    parser.add_argument("--workdir", default=".", help="Project working directory.")
    parser.add_argument("--run-label", default="", help="Optional run folder label.")
    parser.add_argument("--source-folder", default=DEFAULT_SOURCE_FOLDER)
    parser.add_argument("--project-id", default=os.getenv("PROJECT_ID", DEFAULT_PROJECT_ID))
    parser.add_argument("--location", default=os.getenv("LOCATION", DEFAULT_LOCATION))
    parser.add_argument(
        "--model-candidates",
        default=os.getenv("VERTEX_MODEL_CANDIDATES", ",".join(DEFAULT_MODEL_CANDIDATES)),
        help="Comma-separated model candidates in priority order.",
    )
    parser.add_argument("--skip-fill", action="store_true", help="Skip model fill stage.")
    parser.add_argument("--max-unmatched", type=int, default=0, help="Debug limit for unmatched poems.")
    parser.add_argument("--fill-top-k", type=int, default=FILL_TOP_K)
    parser.add_argument("--fill-batch-size", type=int, default=FILL_BATCH_SIZE)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())


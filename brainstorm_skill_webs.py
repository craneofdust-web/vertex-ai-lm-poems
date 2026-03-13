import importlib
import json
import math
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error as urlerror

import vertexai
from google.api_core import exceptions as gcp_exceptions
from vertexai.generative_models import GenerativeModel

BACKEND_ROOT = Path(__file__).resolve().parent / "backend"
if BACKEND_ROOT.is_dir() and str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(_stdout_reconfigure):
    _stdout_reconfigure(encoding="utf-8")
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if callable(_stderr_reconfigure):
    _stderr_reconfigure(encoding="utf-8")

# ==========================================
# 1. 專案設定
# ==========================================
PROJECT_ID = os.getenv("PROJECT_ID", "your-gcp-project-id")
LOCATION = os.getenv("LOCATION", "us-central1")
DEFAULT_MODEL_CANDIDATES = ["gemini-3.1", "gemini-3-pro", "gemini-2.5-pro"]
MODEL_CANDIDATES = [
    model.strip()
    for model in os.getenv("VERTEX_MODEL_CANDIDATES", ",".join(DEFAULT_MODEL_CANDIDATES)).split(",")
    if model.strip()
]

FOLDER_PATH = os.getenv("POEMS_SOURCE_FOLDER", "./sample_poems")
EXCLUDE_DIRS = {".obsidian", ".trash", "Templates"}

# 抽樣策略：30~36 輪 + 覆蓋率導向 + 2/3 上限
SAMPLE_SIZE = int(os.getenv("SAMPLE_SIZE", "50"))
MIN_ITERATIONS = int(os.getenv("MIN_ITERATIONS", "30"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "36"))
TARGET_MIN_COVERAGE = int(os.getenv("TARGET_MIN_COVERAGE", "3"))
MAX_DRAW_RATIO = float(os.getenv("MAX_DRAW_RATIO", str(2 / 3)))

# 生成策略：給模型更高自由度
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.92"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BASE_RETRY_SECONDS = int(os.getenv("BASE_RETRY_SECONDS", "2"))
RANDOM_SEED = None
MIN_CITATIONS_PER_NODE = int(os.getenv("MIN_CITATIONS_PER_NODE", "2"))
MAX_CITATIONS_PER_NODE = int(os.getenv("MAX_CITATIONS_PER_NODE", "4"))
WRITE_MARKDOWN_REPORT = os.getenv("WRITE_MARKDOWN_REPORT", "1") == "1"
WRITE_MOUNTING_INDEX = os.getenv("WRITE_MOUNTING_INDEX", "1") == "1"
STRICT_VALIDATION = os.getenv("STRICT_VALIDATION", "0") == "1"
ETA_POST_SECONDS = int(os.getenv("ETA_POST_SECONDS", "45"))
CONSENSUS_REPORT_PATH = os.getenv("CONSENSUS_REPORT_PATH", "").strip()
SYSTEM_INSTRUCTION_OVERRIDE = os.getenv("SYSTEM_INSTRUCTION_OVERRIDE", "").strip()
SYSTEM_INSTRUCTION_APPEND = os.getenv("SYSTEM_INSTRUCTION_APPEND", "").strip()
SALON_MAX_BULLETS = int(os.getenv("SALON_MAX_BULLETS", "3"))
LLM_BACKEND = os.getenv("LLM_BACKEND", "vertex").strip().lower()
RELAY_MODEL = os.getenv("RELAY_MODEL", "gpt-5.4").strip()
RELAY_REASONING_EFFORT = os.getenv("RELAY_REASONING_EFFORT", "xhigh").strip()
RELAY_TIMEOUT = float(os.getenv("RELAY_TIMEOUT", "240"))
RELAY_MAX_ATTEMPTS = int(os.getenv("RELAY_MAX_ATTEMPTS", "6"))
RELAY_STOP_ON_429 = os.getenv("RELAY_STOP_ON_429", "1") == "1"

SYSTEM_INSTRUCTION = """
你是一位兼具「前衛文學評論家」與「硬核 RPG 系統設計師」雙重身份的專家。
請閱讀我提供的這批詩歌樣本，發想「多維度詩歌創作技能網 (Skill Web)」節點，並且務必附上可對照的引文證據。

【資料夾狀態判定規則】（極度重要！請根據文本標註的「資料夾狀態」採取不同視角）：
1. 狀態為「未整理作品」或類似早期歸檔：這是作者早期的創作或尚未定型的風格。請將其視為技能樹的【基礎天賦 (Lv.1-20)】。請從中萃取出最原始的衝動、早期的模仿痕跡，命名為諸如「古典學徒」、「青澀的感傷」等底層節點。
2. 狀態為「未完成長篇」、「未完成短篇」或「創作中」：這是正在鍛造中的兵器。絕對不要用「完整的詩意」去評判它！請使用【解耦 (Decoupling) 視角】，分析作者正在測試什麼樣的「技藝實驗」或「結構重組」。將其命名為【實驗性法術 / 殘缺的技能頁】，例如「意象解構實驗」、「未定型的長篇史詩感」。
3. 狀態為其他常規詩歌資料夾：視為成熟技能，可歸類為進階轉職或終極奧義。

【設計核心要求】：
1. 專業術語與文學批評：請大量使用文學、哲學、美學的專業術語來命名與描述節點（如：印象主義、現象學觀察、虛無主義抵抗、解構主義、存在主義焦慮等）。
2. 體裁與思維的交錯：請將「詩的體裁（如：十四行詩、唐宋近體）」與「思維方式（如：批判性思考、冷眼旁觀）」都視為獨立技能。必須設計出需要「體裁載體」+「思維被動」雙重前置才能解鎖的複合技能！
3. 想像力解放：不要理會作者原本的 Tag，請大膽創造極具 RPG 風格與學術深度的詞彙。

【引文規則】：
1. 每個節點都必須有 citations 陣列，至少 {min_citations} 筆，至多 {max_citations} 筆。
2. citation.quote 必須是樣本中的「原文連續子字串」，禁止改寫、禁止總結。
3. citation.source_id 必須精確複製我提供的【來源】欄位。
4. citation.why 要簡短說明該句如何支持該節點（1~2 句）。

輸出格式要求 (純 JSON Array)：
[
  {
    "node_id": "英文代號 (如: phenomenological_gaze)",
    "node_name": "極具創意的專業術語或 RPG 技能名",
    "node_tier": "基礎天賦 / 進階轉職 / 實驗原型 / 終極奧義",
    "prerequisite_nodes": ["前置節點的 node_id 1", "前置節點的 node_id 2"],
    "unlock_condition": "解鎖此節點需要的領悟或前置要求",
    "description": "用硬核且專業的文學評論語氣，描述這個技能的特質與威力",
    "citations": [
      {
        "source_id": "詩作的來源 id（必須來自輸入）",
        "source_title": "詩名（可選，但建議填）",
        "folder_status": "該詩的資料夾狀態（可選）",
        "quote": "詩中的原句（原文摘錄，不可改寫）",
        "why": "這句如何支撐此節點的分類/命名"
      }
    ]
  }
]
【絕對禁止】：
1. 不要把所有詩逐首總結。
2. 不要輸出 Markdown，只能輸出 JSON Array。
3. 不要杜撰不存在於樣本的引文。
"""


def select_model(candidates: List[str]) -> Tuple[str, GenerativeModel]:
    if not candidates:
        raise ValueError("MODEL_CANDIDATES 不可為空。")

    last_error: Exception | None = None
    for model_name in candidates:
        try:
            candidate = GenerativeModel(model_name)
            candidate.generate_content(
                "[]",
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0,
                },
            )
            return model_name, candidate
        except (
            gcp_exceptions.InvalidArgument,
            gcp_exceptions.PermissionDenied,
            gcp_exceptions.NotFound,
            gcp_exceptions.ResourceExhausted,
            gcp_exceptions.FailedPrecondition,
        ) as error:
            last_error = error
            print(f"⚠️ 模型 {model_name} 不可用，改試下一個候選。({type(error).__name__})")
        except Exception as error:
            last_error = error
            print(f"⚠️ 模型 {model_name} 探測失敗，改試下一個候選。({type(error).__name__})")

    raise RuntimeError(f"所有候選模型皆不可用，最後錯誤: {last_error}")


def scan_markdown_poems(folder_path: str, exclude_dirs: set) -> List[Dict[str, str]]:
    poems: List[Dict[str, str]] = []
    print(f"開始掃描資料夾 (已套用黑名單過濾): {folder_path}")

    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
        current_folder = os.path.basename(root)

        for filename in files:
            if not filename.endswith(".md"):
                continue
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, folder_path)
            try:
                with open(file_path, "r", encoding="utf-8") as file_obj:
                    poems.append(
                        {
                            "id": relative_path.replace("\\", "/"),
                            "filename": filename,
                            "folder": current_folder,
                            "content": file_obj.read(),
                        }
                    )
            except Exception as error:
                print(f"⚠️ 讀取 {relative_path} 時發生錯誤: {error}")

    return poems


def compute_iteration_count(total_poems: int) -> Tuple[int, int]:
    required_for_target = math.ceil((total_poems * TARGET_MIN_COVERAGE) / SAMPLE_SIZE)
    chosen_iterations = max(MIN_ITERATIONS, min(required_for_target, MAX_ITERATIONS))
    return chosen_iterations, required_for_target


def pick_low_count_items(
    poem_pool: List[Dict[str, str]],
    draw_counts: Dict[str, int],
    k: int,
) -> List[Dict[str, str]]:
    if k <= 0 or not poem_pool:
        return []
    shuffled = list(poem_pool)
    random.shuffle(shuffled)
    shuffled.sort(key=lambda poem: draw_counts[poem["id"]])
    return shuffled[:k]


def select_batch(
    poems: List[Dict[str, str]],
    draw_counts: Dict[str, int],
    sample_size: int,
    target_coverage: int,
    max_draws_per_poem: int,
) -> List[Dict[str, str]]:
    eligible = [poem for poem in poems if draw_counts[poem["id"]] < max_draws_per_poem]
    if not eligible:
        return []

    need_more = [poem for poem in eligible if draw_counts[poem["id"]] < target_coverage]
    batch = pick_low_count_items(need_more, draw_counts, min(sample_size, len(need_more)))
    selected_ids = {poem["id"] for poem in batch}

    if len(batch) < sample_size:
        remaining_eligible = [poem for poem in eligible if poem["id"] not in selected_ids]
        batch.extend(
            pick_low_count_items(
                remaining_eligible,
                draw_counts,
                min(sample_size - len(batch), len(remaining_eligible)),
            )
        )

    return batch


def _clip_list(items: Any, limit: int) -> List[str]:
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _format_salon_summary(payload: Dict[str, Any]) -> str:
    consensus = str(payload.get("consensus") or "").strip()
    stance_counts = payload.get("stance_counts", {}) if isinstance(payload.get("stance_counts"), dict) else {}
    lines = []
    if consensus:
        lines.append(f"- consensus: {consensus}")
    if stance_counts:
        stance_bits = ", ".join(f"{k}:{v}" for k, v in stance_counts.items())
        lines.append(f"- stance_counts: {stance_bits}")
    for label, key in (
        ("what_works", "what_works"),
        ("structural_gaps", "structural_gaps"),
        ("anticipated_later_work", "anticipated_later_work"),
    ):
        items = _clip_list(payload.get(key), SALON_MAX_BULLETS)
        if not items:
            continue
        lines.append(f"- {label}:")
        for item in items:
            lines.append(f"  - {item}")
    return "\n".join(lines).strip()


def _load_consensus_map(path: str) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
    except Exception as error:
        print(f"⚠️ 無法讀取評審會報告: {error}")
        return {}
    targets = data.get("targets", []) if isinstance(data, dict) else []
    if not isinstance(targets, list):
        return {}
    return {
        str(item.get("target_id") or "").strip(): item
        for item in targets
        if isinstance(item, dict) and str(item.get("target_id") or "").strip()
    }


def build_batch_text(sampled_poems: List[Dict[str, str]], consensus_by_id: Dict[str, Dict[str, Any]] | None = None) -> str:
    blocks = []
    for poem in sampled_poems:
        consensus_payload = consensus_by_id.get(poem["id"]) if consensus_by_id else None
        salon_block = ""
        if isinstance(consensus_payload, dict):
            summary = _format_salon_summary(consensus_payload)
            if summary:
                salon_block = f"\n【評審會摘要】\n{summary}\n"
        blocks.append(
            f"【篇名：{poem['filename']}】\n"
            f"【資料夾狀態：{poem['folder']}】\n"
            f"【來源：{poem['id']}】\n"
            f"{poem['content']}"
            f"{salon_block}"
        )
    separator = "\n" + "=" * 30 + "\n"
    return separator.join(blocks) + "\n"


def parse_json_response(raw_text: str):
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _extract_json_array(raw_text: str) -> list[dict[str, Any]]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "[":
            continue
        try:
            payload, _ = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            return payload
    raise ValueError("no valid JSON array found in response text")


def _parse_json_array_response(raw_text: str) -> list[dict[str, Any]]:
    parsed = parse_json_response(raw_text)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        nodes = parsed.get("nodes")
        if isinstance(nodes, list):
            return nodes
    return _extract_json_array(raw_text)


def _load_relay_dependencies():
    try:
        responses_relay = importlib.import_module("app.responses_relay")
        relay_profile = importlib.import_module("app.relay_profile")
    except Exception as exc:
        raise RuntimeError("relay backend unavailable") from exc
    return (
        responses_relay.build_responses_payload,
        responses_relay.post_responses_stream,
        relay_profile.resolve_base_url,
        relay_profile.resolve_api_key,
    )


def render_system_instruction() -> str:
    base = SYSTEM_INSTRUCTION.replace("{min_citations}", str(MIN_CITATIONS_PER_NODE)).replace(
        "{max_citations}", str(MAX_CITATIONS_PER_NODE)
    )
    if SYSTEM_INSTRUCTION_OVERRIDE:
        base = SYSTEM_INSTRUCTION_OVERRIDE
    if SYSTEM_INSTRUCTION_APPEND:
        base = f"{base}\n\n{SYSTEM_INSTRUCTION_APPEND}".strip()
    return base


def normalize_for_match(text: str) -> str:
    return " ".join(text.split())


def canonicalize_text(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE).lower()


def quote_in_source(quote: str, source_content: str) -> bool:
    if quote in source_content:
        return True
    if normalize_for_match(quote) in normalize_for_match(source_content):
        return True
    quote_canonical = canonicalize_text(quote)
    source_canonical = canonicalize_text(source_content)
    return bool(quote_canonical) and quote_canonical in source_canonical


def repair_quote(quote: str, source_content: str) -> str | None:
    quote_clean = quote.strip().strip("「」『』\"'`")
    if not quote_clean:
        return None
    if quote_in_source(quote_clean, source_content):
        return quote_clean

    lines = [line.strip() for line in source_content.splitlines() if line.strip()]
    if not lines:
        return None

    segments = [
        seg.strip() for seg in re.split(r"(?:\.{3,}|…+)", quote_clean) if seg.strip()
    ]
    if segments:
        segment_can = [canonicalize_text(seg) for seg in segments if canonicalize_text(seg)]
        for line in lines:
            line_can = canonicalize_text(line)
            if line_can and all(seg in line_can for seg in segment_can):
                return line

    quote_can = canonicalize_text(quote_clean)
    if not quote_can:
        return None

    best_line = ""
    best_score = 0.0
    for line in lines:
        line_can = canonicalize_text(line)
        if not line_can:
            continue
        if quote_can in line_can:
            return line
        score = SequenceMatcher(None, quote_can, line_can).ratio()
        if score > best_score:
            best_score = score
            best_line = line

    if best_score >= 0.72:
        return best_line
    return None


def build_poem_index(sampled_poems: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {poem["id"]: poem for poem in sampled_poems}


def validate_fragment(
    fragment: Any,
    poem_index: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    if isinstance(fragment, dict):
        nodes = fragment.get("nodes")
        if isinstance(nodes, list):
            fragment = nodes
    if not isinstance(fragment, list):
        raise ValueError("模型回傳不是 JSON Array。")

    errors: List[str] = []
    warnings: List[str] = []
    normalized_nodes: List[Dict[str, Any]] = []
    required_fields = [
        "node_id",
        "node_name",
        "node_tier",
        "prerequisite_nodes",
        "unlock_condition",
        "description",
        "citations",
    ]

    for idx, node in enumerate(fragment):
        node_label = f"node[{idx}]"
        if not isinstance(node, dict):
            if STRICT_VALIDATION:
                errors.append(f"{node_label} 不是物件")
            else:
                warnings.append(f"{node_label} 不是物件，已略過")
            continue

        for field in required_fields:
            if field not in node:
                if STRICT_VALIDATION:
                    errors.append(f"{node_label} 缺少欄位 {field}")
                else:
                    warnings.append(f"{node_label} 缺少欄位 {field}")

        citations = node.get("citations", [])
        if not isinstance(citations, list):
            if STRICT_VALIDATION:
                errors.append(f"{node_label}.citations 不是陣列")
            else:
                warnings.append(f"{node_label}.citations 不是陣列，已重置為空陣列")
            citations = []

        normalized_citations: List[Dict[str, str]] = []
        for c_idx, citation in enumerate(citations[:MAX_CITATIONS_PER_NODE]):
            citation_label = f"{node_label}.citations[{c_idx}]"
            if not isinstance(citation, dict):
                if STRICT_VALIDATION:
                    errors.append(f"{citation_label} 不是物件")
                else:
                    warnings.append(f"{citation_label} 不是物件，已略過")
                continue

            source_id = str(citation.get("source_id", "")).strip()
            quote = str(citation.get("quote", "")).strip()
            why = str(citation.get("why", "")).strip()
            source_title = str(citation.get("source_title", "")).strip()
            folder_status = str(citation.get("folder_status", "")).strip()

            if not source_id:
                if STRICT_VALIDATION:
                    errors.append(f"{citation_label} 缺少 source_id")
                else:
                    warnings.append(f"{citation_label} 缺少 source_id，已略過")
                    continue
            elif source_id not in poem_index:
                if STRICT_VALIDATION:
                    errors.append(f"{citation_label} source_id 不在本輪樣本: {source_id}")
                else:
                    warnings.append(f"{citation_label} source_id 不在本輪樣本，已略過")
                    continue
            if not quote:
                if STRICT_VALIDATION:
                    errors.append(f"{citation_label} 缺少 quote")
                else:
                    warnings.append(f"{citation_label} 缺少 quote，已略過")
                    continue
            if not why:
                if STRICT_VALIDATION:
                    errors.append(f"{citation_label} 缺少 why")
                else:
                    why = "引文與節點語義相符（自動補全說明）"

            if source_id in poem_index and quote:
                source_content = poem_index[source_id]["content"]
                repaired_quote = repair_quote(quote, source_content)
                if repaired_quote is None:
                    if STRICT_VALIDATION:
                        errors.append(f"{citation_label} quote 不存在於 source_id 對應原文")
                    else:
                        warnings.append(f"{citation_label} quote 無法對應原文，已略過")
                        continue
                else:
                    quote = repaired_quote

            if source_id in poem_index:
                if not source_title:
                    source_title = poem_index[source_id]["filename"]
                if not folder_status:
                    folder_status = poem_index[source_id]["folder"]

            normalized_citations.append(
                {
                    "source_id": source_id,
                    "source_title": source_title,
                    "folder_status": folder_status,
                    "quote": quote,
                    "why": why,
                }
            )

        if len(normalized_citations) < MIN_CITATIONS_PER_NODE:
            if STRICT_VALIDATION:
                errors.append(f"{node_label}.citations 少於 {MIN_CITATIONS_PER_NODE} 筆")
                continue
            if not normalized_citations:
                warnings.append(f"{node_label} 無有效 citations，已略過節點")
                continue
            warnings.append(
                f"{node_label}.citations 不足 {MIN_CITATIONS_PER_NODE} 筆，保留 {len(normalized_citations)} 筆"
            )

        prerequisite_nodes = node.get("prerequisite_nodes", [])
        if not isinstance(prerequisite_nodes, list):
            if STRICT_VALIDATION:
                errors.append(f"{node_label}.prerequisite_nodes 不是陣列")
                prerequisite_nodes = []
            else:
                warnings.append(f"{node_label}.prerequisite_nodes 不是陣列，已轉為空陣列")
                prerequisite_nodes = []

        normalized_nodes.append(
            {
                "node_id": str(node.get("node_id", "")).strip(),
                "node_name": str(node.get("node_name", "")).strip(),
                "node_tier": str(node.get("node_tier", "")).strip(),
                "prerequisite_nodes": prerequisite_nodes,
                "unlock_condition": str(node.get("unlock_condition", "")).strip(),
                "description": str(node.get("description", "")).strip(),
                "citations": normalized_citations,
            }
        )

    if STRICT_VALIDATION and errors:
        preview = "; ".join(errors[:5])
        raise ValueError(f"輸出驗證失敗，共 {len(errors)} 項問題：{preview}")
    if not normalized_nodes:
        if errors:
            preview = "; ".join(errors[:5])
            raise ValueError(f"輸出驗證失敗，無可用節點。示例錯誤：{preview}")
        raise ValueError("輸出驗證失敗，無可用節點。")
    if warnings:
        preview = "; ".join(warnings[:3])
        print(f"[warn] 驗證警告 {len(warnings)} 項（已自動修復/略過部分內容）：{preview}")

    return normalized_nodes


def write_markdown_fragment(fragment: List[Dict[str, Any]], output_path: str) -> None:
    lines: List[str] = ["# Skill Web Fragment（附引文）", ""]
    footnotes: List[str] = []
    footnote_idx = 1

    for idx, node in enumerate(fragment, start=1):
        lines.append(f"## {idx}. {node['node_name']} (`{node['node_id']}`)")
        lines.append(f"- `tier`: {node['node_tier']}")
        lines.append(f"- `unlock_condition`: {node['unlock_condition']}")
        lines.append(f"- `description`: {node['description']}")

        prerequisites = node.get("prerequisite_nodes") or []
        if isinstance(prerequisites, list) and prerequisites:
            lines.append(f"- `prerequisite_nodes`: {', '.join(map(str, prerequisites))}")
        else:
            lines.append("- `prerequisite_nodes`: （無）")

        citation_refs: List[str] = []
        for citation in node.get("citations", []):
            ref = f"[^{footnote_idx}]"
            citation_refs.append(ref)
            quote = normalize_for_match(str(citation.get("quote", "")))
            source_id = str(citation.get("source_id", ""))
            source_title = str(citation.get("source_title", ""))
            why = normalize_for_match(str(citation.get("why", "")))
            footnotes.append(
                f"[^{footnote_idx}]: `{source_id}` {source_title} 「{quote}」；理由：{why}"
            )
            footnote_idx += 1

        lines.append(
            f"- `citations`: {' '.join(citation_refs) if citation_refs else '（無）'}"
        )
        lines.append("")

    if footnotes:
        lines.append("---")
        lines.append("")
        lines.extend(footnotes)

    with open(output_path, "w", encoding="utf-8") as file_obj:
        file_obj.write("\n".join(lines) + "\n")


def generate_fragment(
    model: GenerativeModel,
    batch_text: str,
    sampled_poems: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    prompt = f"{render_system_instruction()}\n\n【本次隨機抽樣的詩歌文本】：\n{batch_text}"
    poem_index = build_poem_index(sampled_poems)
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": TEMPERATURE,
                },
            )
            parsed = parse_json_response(response.text)
            return validate_fragment(parsed, poem_index)
        except (
            gcp_exceptions.ResourceExhausted,
            gcp_exceptions.ServiceUnavailable,
            gcp_exceptions.DeadlineExceeded,
        ) as error:
            last_error = error
            if attempt == MAX_RETRIES:
                break
            sleep_seconds = BASE_RETRY_SECONDS * (2 ** (attempt - 1))
            print(f"⚠️ API 暫時不可用，{sleep_seconds} 秒後重試 (第 {attempt}/{MAX_RETRIES} 次)...")
            time.sleep(sleep_seconds)
        except (json.JSONDecodeError, ValueError, gcp_exceptions.InvalidArgument) as error:
            last_error = error
            if attempt == MAX_RETRIES:
                break
            print(f"⚠️ 回傳格式異常，準備重試 (第 {attempt}/{MAX_RETRIES} 次)...")

    assert last_error is not None
    raise last_error


def generate_fragment_relay(
    batch_text: str,
    sampled_poems: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    prompt = f"{render_system_instruction()}\n\n【本次隨機抽樣的詩歌文本】：\n{batch_text}"
    poem_index = build_poem_index(sampled_poems)
    build_responses_payload, post_responses_stream, resolve_base_url, resolve_api_key = _load_relay_dependencies()
    base_url = resolve_base_url(env=os.environ)
    api_key = resolve_api_key(env=os.environ)
    if not base_url or not api_key:
        raise ValueError("missing relay base_url or api_key")
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            payload = build_responses_payload(
                {"messages": [{"role": "user", "content": prompt}]},
                model=RELAY_MODEL,
                reasoning_effort=RELAY_REASONING_EFFORT,
            )
            response_text = post_responses_stream(
                base_url=base_url,
                api_key=api_key,
                payload=payload,
                timeout=RELAY_TIMEOUT,
                max_attempts=max(1, int(RELAY_MAX_ATTEMPTS)),
                stop_on_status=[429] if RELAY_STOP_ON_429 else None,
            )
            parsed = _parse_json_array_response(response_text)
            return validate_fragment(parsed, poem_index)
        except urlerror.HTTPError as error:
            last_error = error
            status = int(getattr(error, "code", 0) or 0)
            if status == 429 and RELAY_STOP_ON_429:
                raise
            if attempt == MAX_RETRIES:
                break
            sleep_seconds = BASE_RETRY_SECONDS * (2 ** (attempt - 1))
            print(f"[warn] relay http {status or 'error'}, retrying in {sleep_seconds}s")
            time.sleep(sleep_seconds)
        except (json.JSONDecodeError, ValueError) as error:
            last_error = error
            if attempt == MAX_RETRIES:
                break
            print(f"[warn] response parse error, retrying ({attempt}/{MAX_RETRIES})")
        except Exception as error:
            last_error = error
            if attempt == MAX_RETRIES:
                break
            print(f"[warn] relay failure, retrying ({attempt}/{MAX_RETRIES})")

    assert last_error is not None
    raise last_error


def print_coverage_summary(draw_counts: Dict[str, int], target_coverage: int) -> None:
    counts = list(draw_counts.values())
    if not counts:
        return

    min_count = min(counts)
    max_count = max(counts)
    avg_count = sum(counts) / len(counts)
    below_target = sum(1 for count in counts if count < target_coverage)
    at_least_once = sum(1 for count in counts if count >= 1)

    print("\n=== 抽樣覆蓋摘要 ===")
    print(f"總詩作數: {len(counts)}")
    print(f"至少抽到 1 次: {at_least_once} 首")
    print(f"低於目標覆蓋 ({target_coverage} 次): {below_target} 首")
    print(f"最少抽樣次數: {min_count}")
    print(f"最多抽樣次數: {max_count}")
    print(f"平均抽樣次數: {avg_count:.2f}")


def format_seconds_to_hm(seconds: float) -> str:
    total_minutes = max(0, int(round(seconds / 60)))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours} 小時 {minutes} 分鐘"


def print_eta(
    round_durations: List[float],
    rounds_done: int,
    total_rounds: int,
    post_seconds: float,
) -> None:
    if rounds_done < 2:
        return
    if not round_durations:
        return

    avg_round_seconds = sum(round_durations) / len(round_durations)
    remaining_rounds = max(0, total_rounds - rounds_done)
    remaining_seconds = (avg_round_seconds * remaining_rounds) + post_seconds
    finish_time = datetime.now() + timedelta(seconds=remaining_seconds)

    print("\n=== 進度預估 (ETA) ===")
    print(
        f"已完成輪次: {rounds_done}/{total_rounds}，"
        f"平均每輪: {format_seconds_to_hm(avg_round_seconds)}"
    )
    print(f"預估剩餘時間: {format_seconds_to_hm(remaining_seconds)}")
    print(f"其中後續填入/掛載索引估計: {format_seconds_to_hm(post_seconds)}")
    print(f"預估完成時間(本地): {finish_time.strftime('%Y-%m-%d %H:%M')}")


def build_mounting_index(
    all_poems: List[Dict[str, str]],
    generated_fragments: List[Tuple[str, List[Dict[str, Any]]]],
) -> List[Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {
        poem["id"]: {
            "source_id": poem["id"],
            "source_title": poem["filename"],
            "folder_status": poem["folder"],
            "matched_nodes": [],
        }
        for poem in all_poems
    }

    for fragment_file, fragment in generated_fragments:
        for node in fragment:
            for citation in node.get("citations", []):
                source_id = citation.get("source_id", "")
                if source_id not in records:
                    continue
                records[source_id]["matched_nodes"].append(
                    {
                        "fragment_file": fragment_file,
                        "node_id": node.get("node_id", ""),
                        "node_name": node.get("node_name", ""),
                        "node_tier": node.get("node_tier", ""),
                        "quote": citation.get("quote", ""),
                        "why": citation.get("why", ""),
                    }
                )

    for record in records.values():
        deduped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for match in record["matched_nodes"]:
            key = (
                str(match.get("node_id", "")),
                str(match.get("fragment_file", "")),
                str(match.get("quote", "")),
            )
            deduped[key] = match
        record["matched_nodes"] = sorted(
            deduped.values(),
            key=lambda item: (item.get("node_tier", ""), item.get("node_name", "")),
        )
        record["match_count"] = len(record["matched_nodes"])

    return sorted(records.values(), key=lambda item: item["source_id"])


def write_mounting_markdown(records: List[Dict[str, Any]], output_path: str) -> None:
    lines: List[str] = ["# Poem Mounting Index（含引文）", ""]
    footnotes: List[str] = []
    footnote_idx = 1

    for record in records:
        source_id = record["source_id"]
        source_title = record["source_title"]
        folder_status = record["folder_status"]
        matched_nodes = record.get("matched_nodes", [])

        lines.append(f"## {source_title}")
        lines.append(f"- `source_id`: {source_id}")
        lines.append(f"- `folder_status`: {folder_status}")
        lines.append(f"- `matched_nodes`: {len(matched_nodes)}")

        if not matched_nodes:
            lines.append("- 無對應節點")
            lines.append("")
            continue

        for node_match in matched_nodes:
            ref = f"[^{footnote_idx}]"
            lines.append(
                f"- `{node_match['node_tier']}` {node_match['node_name']} (`{node_match['node_id']}`) {ref}"
            )
            quote = normalize_for_match(str(node_match.get("quote", "")))
            why = normalize_for_match(str(node_match.get("why", "")))
            fragment_file = str(node_match.get("fragment_file", ""))
            footnotes.append(
                f"[^{footnote_idx}]: 來源 `{fragment_file}`；引文：「{quote}」；說明：{why}"
            )
            footnote_idx += 1

        lines.append("")

    if footnotes:
        lines.append("---")
        lines.append("")
        lines.extend(footnotes)

    with open(output_path, "w", encoding="utf-8") as file_obj:
        file_obj.write("\n".join(lines) + "\n")


def main() -> None:
    if MIN_ITERATIONS > MAX_ITERATIONS:
        raise ValueError("MIN_ITERATIONS 不可大於 MAX_ITERATIONS。")
    if MIN_CITATIONS_PER_NODE > MAX_CITATIONS_PER_NODE:
        raise ValueError("MIN_CITATIONS_PER_NODE 不可大於 MAX_CITATIONS_PER_NODE。")

    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    model = None
    backend = LLM_BACKEND or "vertex"
    if backend == "relay":
        print(f"[info] backend=relay model={RELAY_MODEL}")
    else:
        print(f"正在初始化 Vertex AI (專案: {PROJECT_ID})...")
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        print(f"模型候選順序: {MODEL_CANDIDATES}")
        model_name, model = select_model(MODEL_CANDIDATES)
        print(f"已選定模型: {model_name}")

    all_poems = scan_markdown_poems(FOLDER_PATH, EXCLUDE_DIRS)
    file_count = len(all_poems)
    print(f"✅ 成功讀取 {file_count} 篇 Markdown 詩歌。")
    consensus_by_id = _load_consensus_map(CONSENSUS_REPORT_PATH)
    if consensus_by_id:
        print(f"✅ 已載入評審會摘要: {len(consensus_by_id)} 篇")

    if file_count == 0:
        print("警告：沒有找到任何 Markdown 檔案，程式終止。")
        return

    iterations, required_for_target = compute_iteration_count(file_count)
    max_draws_per_poem = max(1, math.floor(iterations * MAX_DRAW_RATIO))
    max_theoretical_avg = (iterations * SAMPLE_SIZE) / file_count

    print("\n=== 本次抽樣策略 ===")
    print(f"SAMPLE_SIZE: {SAMPLE_SIZE}")
    print(f"ITERATIONS: {iterations} (允許範圍 {MIN_ITERATIONS}~{MAX_ITERATIONS})")
    print(f"目標最低覆蓋: 每首至少 {TARGET_MIN_COVERAGE} 次")
    print(f"單首上限: floor(ITERATIONS * 2/3) = {max_draws_per_poem} 次")
    print(f"理論平均覆蓋: {max_theoretical_avg:.2f} 次/首")

    if required_for_target > MAX_ITERATIONS:
        print(
            f"⚠️ 若要達到每首至少 {TARGET_MIN_COVERAGE} 次，"
            f"理論上需至少 {required_for_target} 輪。"
            f"目前上限為 {MAX_ITERATIONS} 輪，將優先追求均勻覆蓋。"
        )
    if not STRICT_VALIDATION:
        print("驗證模式: lenient（會自動修復引用與略過無效節點，避免整輪失敗）")
    else:
        print("驗證模式: strict（任何不合規節點都會觸發失敗）")
    eta_post_seconds = ETA_POST_SECONDS if WRITE_MOUNTING_INDEX else 0

    sampled_counts = {poem["id"]: 0 for poem in all_poems}
    successful_counts = {poem["id"]: 0 for poem in all_poems}
    generated_count = 0
    generated_fragments: List[Tuple[str, List[Dict[str, Any]]]] = []
    round_durations: List[float] = []
    interrupted = False

    for i in range(iterations):
        round_start = time.time()
        sampled_poems = select_batch(
            poems=all_poems,
            draw_counts=sampled_counts,
            sample_size=SAMPLE_SIZE,
            target_coverage=TARGET_MIN_COVERAGE,
            max_draws_per_poem=max_draws_per_poem,
        )

        if not sampled_poems:
            print(f"⚠️ 第 {i+1} 輪無可用樣本（皆達上限），提前停止。")
            break

        print(f"\n--- 開始生成第 {i+1} 份局部技能譜系（樣本數: {len(sampled_poems)}）---")
        batch_text = build_batch_text(sampled_poems, consensus_by_id)
        for poem in sampled_poems:
            sampled_counts[poem["id"]] += 1

        try:
            if backend == "relay":
                fragment = generate_fragment_relay(batch_text, sampled_poems)
            else:
                assert model is not None
                fragment = generate_fragment(model, batch_text, sampled_poems)
            output_json = f"skill_web_fragment_{i+1}.json"
            output_md = ""
            with open(output_json, "w", encoding="utf-8") as file_obj:
                json.dump(fragment, file_obj, ensure_ascii=False, indent=2)
            if WRITE_MARKDOWN_REPORT:
                output_md = f"skill_web_fragment_{i+1}.md"
                write_markdown_fragment(fragment, output_md)
            generated_fragments.append((output_json, fragment))
            for poem in sampled_poems:
                successful_counts[poem["id"]] += 1
            generated_count += 1
            if WRITE_MARKDOWN_REPORT and output_md:
                print(f"✅ 第 {i+1} 份局部譜系已儲存為 {output_json} / {output_md}")
            else:
                print(f"✅ 第 {i+1} 份局部譜系已儲存為 {output_json}")
        except KeyboardInterrupt:
            interrupted = True
            print("\n⏹️ 偵測到手動中斷，將保留已完成輸出並結束流程。")
            break
        except Exception as error:
            print(f"❌ 第 {i+1} 輪生成失敗: {error}")
        finally:
            round_seconds = time.time() - round_start
            round_durations.append(round_seconds)
            if i + 1 >= 2:
                print_eta(
                    round_durations=round_durations,
                    rounds_done=i + 1,
                    total_rounds=iterations,
                    post_seconds=eta_post_seconds,
                )

        if interrupted:
            break

    if WRITE_MOUNTING_INDEX and generated_fragments:
        mounting_records = build_mounting_index(all_poems, generated_fragments)
        mounting_json = "poem_mounting_index.json"
        with open(mounting_json, "w", encoding="utf-8") as file_obj:
            json.dump(mounting_records, file_obj, ensure_ascii=False, indent=2)
        mounting_md = "poem_mounting_index.md"
        write_mounting_markdown(mounting_records, mounting_md)
        print(f"\n✅ 已輸出掛載索引: {mounting_json} / {mounting_md}")

    print("\n=== 成功掛載覆蓋（僅成功輪次） ===")
    print_coverage_summary(successful_counts, TARGET_MIN_COVERAGE)
    print("\n=== 抽樣覆蓋（包含失敗輪次） ===")
    print_coverage_summary(sampled_counts, TARGET_MIN_COVERAGE)
    print(f"\n🎉 已完成 {generated_count} 份局部譜系。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ 流程已由使用者中止。")


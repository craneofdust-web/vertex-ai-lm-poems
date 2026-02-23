import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


TIER_ORDER = ["基礎天賦", "實驗原型", "進階轉職", "終極奧義"]
DEFAULT_MASTER = Path("master_skill_web.json")
DEFAULT_OUT_DIR = Path("visualizations")
DEFAULT_POEMS_ROOT = Path(os.getenv("POEMS_ROOT", "")).expanduser() if os.getenv("POEMS_ROOT") else None
LANE_LABELS = {"craft": "技法進化", "hybrid": "交叉進化", "theme": "題材進化"}

CRAFT_KEYWORDS = (
    "格律",
    "對仗",
    "押韻",
    "韻律",
    "修辭",
    "句法",
    "語法",
    "節奏",
    "結構",
    "章法",
    "形式",
    "敘事技法",
    "metaphor",
    "syntax",
    "rhythm",
    "meter",
    "imagery construction",
)

THEME_KEYWORDS = (
    "主題",
    "題材",
    "意象",
    "情感",
    "歷史",
    "神話",
    "自然",
    "山水",
    "季節",
    "愛情",
    "孤獨",
    "哲思",
    "政治",
    "文明",
    "敘事世界",
    "theme",
    "myth",
    "narrative world",
)


def detect_default_master() -> Path:
    runtime_root = Path("runtime_workspaces")
    if runtime_root.exists():
        workspaces = sorted(
            [item for item in runtime_root.iterdir() if item.is_dir()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for workspace in workspaces:
            candidate = workspace / "runs" / workspace.name / "master_skill_web.json"
            if candidate.exists():
                return candidate

    legacy_root = Path("runs")
    if legacy_root.exists():
        run_dirs = sorted(
            [item for item in legacy_root.iterdir() if item.is_dir()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for run_dir in run_dirs:
            candidate = run_dir / "master_skill_web.json"
            if candidate.exists():
                return candidate

    return DEFAULT_MASTER


DEFAULT_MASTER = detect_default_master()


def load_master(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if not isinstance(data, list):
        raise ValueError(f"master file is not an array: {path}")
    return data


def compute_depths(prereq_map: Dict[str, List[str]]) -> Dict[str, int]:
    memo: Dict[str, int] = {}

    def dfs(node_id: str, stack: set[str]) -> int:
        if node_id in memo:
            return memo[node_id]
        if node_id in stack:
            return 0
        prereq = prereq_map.get(node_id, [])
        if not prereq:
            memo[node_id] = 0
            return 0
        next_stack = set(stack)
        next_stack.add(node_id)
        depth = 1 + max(dfs(parent_id, next_stack) for parent_id in prereq)
        memo[node_id] = depth
        return depth

    for node_id in prereq_map:
        dfs(node_id, set())
    return memo


def compute_stages(
    nodes: List[Dict[str, Any]],
    base_depth: Dict[str, int],
    max_per_stage: int = 8,
) -> Dict[str, int]:
    stages: Dict[str, int] = {node["id"]: int(base_depth.get(node["id"], 0)) for node in nodes}

    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for node in nodes:
        depth = int(stages[node["id"]])
        grouped.setdefault(depth, []).append(node)

    for depth in sorted(grouped.keys()):
        group = grouped[depth]
        group.sort(
            key=lambda node: (
                -int(node.get("support_count", 0)),
                str(node.get("name", "")),
            )
        )
        for idx, node in enumerate(group):
            stages[node["id"]] = max(stages[node["id"]], depth + idx // max_per_stage)

    changed = True
    while changed:
        changed = False
        for node in nodes:
            target_id = node["id"]
            required_stage = stages[target_id]
            for source_id in node.get("prerequisites", []):
                required_stage = max(required_stage, int(stages.get(source_id, 0)) + 1)
            if required_stage != stages[target_id]:
                stages[target_id] = required_stage
                changed = True
    return stages


def infer_lane(node_name: str, description: str) -> str:
    text = f"{node_name} {description}".lower()
    craft_score = sum(text.count(keyword.lower()) for keyword in CRAFT_KEYWORDS)
    theme_score = sum(text.count(keyword.lower()) for keyword in THEME_KEYWORDS)
    if craft_score >= theme_score + 1:
        return "craft"
    if theme_score >= craft_score + 1:
        return "theme"
    return "hybrid"


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp950"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def strip_frontmatter(text: str) -> str:
    content = text.replace("\r\n", "\n").strip()
    if not content.startswith("---\n"):
        return content
    closing = content.find("\n---\n", 4)
    if closing == -1:
        return content
    return content[closing + 5 :].strip()


def build_source_text_map(
    master_nodes: List[Dict[str, Any]],
    poems_root: Optional[Path],
    max_chars: int = 2400,
) -> Dict[str, str]:
    if poems_root is None or not poems_root.exists():
        return {}

    source_ids: Set[str] = set()
    for node in master_nodes:
        citations = node.get("citations", [])
        if not isinstance(citations, list):
            continue
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            source_id = str(citation.get("source_id", "")).strip()
            if source_id:
                source_ids.add(source_id)

    source_texts: Dict[str, str] = {}
    for source_id in sorted(source_ids):
        candidate = poems_root.joinpath(*source_id.split("/"))
        if not candidate.exists():
            alt = poems_root / source_id
            if alt.exists():
                candidate = alt
            else:
                continue
        if not candidate.is_file():
            continue
        try:
            poem_text = strip_frontmatter(read_text_with_fallback(candidate))
        except OSError:
            continue
        if not poem_text:
            continue
        source_texts[source_id] = poem_text[:max_chars]
    return source_texts


def prepare_data(
    master_nodes: List[Dict[str, Any]],
    stage_bucket_size: int = 8,
    source_texts: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    node_ids = {str(node.get("node_id", "")).strip() for node in master_nodes}
    nodes: List[Dict[str, Any]] = []

    prereq_map: Dict[str, List[str]] = {}
    for node in master_nodes:
        node_id = str(node.get("node_id", "")).strip()
        if not node_id:
            continue
        tier = str(node.get("node_tier", "")).strip()
        if tier not in TIER_ORDER:
            tier = "進階轉職"
        prereq = node.get("prerequisite_nodes", [])
        if not isinstance(prereq, list):
            prereq = []
        cleaned_prereq = [
            str(p).strip() for p in prereq if str(p).strip() and str(p).strip() in node_ids
        ]
        prereq_map[node_id] = cleaned_prereq
        citations_raw = node.get("citations", [])
        citations: List[Dict[str, str]] = []
        if isinstance(citations_raw, list):
            for citation in citations_raw[:4]:
                if not isinstance(citation, dict):
                    continue
                citations.append(
                    {
                        "source_id": str(citation.get("source_id", "")).strip(),
                        "source_title": str(citation.get("source_title", "")).strip(),
                        "quote": str(citation.get("quote", "")).strip(),
                        "why": str(citation.get("why", "")).strip(),
                    }
                )
        nodes.append(
            {
                "id": node_id,
                "name": str(node.get("node_name", "")).strip(),
                "tier": tier,
                "unlock_condition": str(node.get("unlock_condition", "")).strip(),
                "description": str(node.get("description", "")).strip(),
                "prerequisites": cleaned_prereq,
                "support_count": int(node.get("metadata", {}).get("support_count", 0)),
                "citations": citations,
                "lane": infer_lane(
                    str(node.get("node_name", "")).strip(),
                    str(node.get("description", "")).strip(),
                ),
            }
        )
    depth_map = compute_depths(prereq_map)
    stage_map = compute_stages(nodes, depth_map, max_per_stage=max(2, stage_bucket_size))
    support_by_id = {node["id"]: int(node.get("support_count", 0)) for node in nodes}
    links: List[Dict[str, str]] = []
    weak_links_total = 0

    for node in nodes:
        node["depth"] = int(depth_map.get(node["id"], 0))
        node["stage"] = int(stage_map.get(node["id"], node["depth"]))
        prereq_sorted = sorted(
            list(node["prerequisites"]),
            key=lambda parent_id: (
                -int(depth_map.get(parent_id, 0)),
                -int(support_by_id.get(parent_id, 0)),
                parent_id,
            ),
        )
        primary = prereq_sorted[:1]
        weak = prereq_sorted[1:]
        node["primary_prerequisites"] = primary
        node["weak_prerequisites"] = weak
        weak_links_total += len(weak)
        for source in primary:
            links.append({"source": source, "target": node["id"]})

    max_depth = max((node["depth"] for node in nodes), default=0)
    max_stage = max((node["stage"] for node in nodes), default=0)
    return {
        "tiers": TIER_ORDER,
        "lane_labels": LANE_LABELS,
        "nodes": nodes,
        "links": links,
        "max_depth": max_depth,
        "max_stage": max_stage,
        "weak_links_total": weak_links_total,
        "source_texts": source_texts or {},
    }


def variant_theme_css(kind: str) -> str:
    if kind == "pixel":
        return """
:root {
  --bg-a: #111326;
  --bg-b: #1f2a44;
  --panel: #0f172a;
  --panel-2: #172554;
  --ink: #f8fafc;
  --muted: #a5b4fc;
  --line: #93c5fd;
  --accent: #22d3ee;
  --tier-0: #38bdf8;
  --tier-1: #22c55e;
  --tier-2: #f59e0b;
  --tier-3: #f97316;
}
body {
  font-family: "Press Start 2P", "Noto Sans TC", monospace;
  background:
    radial-gradient(circle at 12% 18%, rgba(34, 211, 238, 0.15), transparent 35%),
    linear-gradient(135deg, var(--bg-a), var(--bg-b));
}
.topbar, .sidepanel {
  border: 3px solid #60a5fa;
  box-shadow: 0 0 0 3px rgba(15, 23, 42, 0.75), 0 14px 28px rgba(2, 6, 23, 0.55);
}
.node {
  border: 3px solid #93c5fd;
  box-shadow: inset 0 0 0 2px rgba(15, 23, 42, 0.8), 0 8px 18px rgba(8, 47, 73, 0.45);
  border-radius: 4px;
}
.link {
  stroke-dasharray: 6 6;
}
"""
    if kind in {"civ", "civ_depth", "civ_rotated", "civ_rotated_lanes"}:
        return """
:root {
  --bg-a: #f4e5c7;
  --bg-b: #d6bd92;
  --panel: #f8f1df;
  --panel-2: #e7d1a8;
  --ink: #2a1808;
  --muted: #5b4631;
  --line: #8b5e34;
  --accent: #9a3412;
  --tier-0: #7c3aed;
  --tier-1: #0f766e;
  --tier-2: #92400e;
  --tier-3: #b91c1c;
}
body {
  font-family: "Cinzel", "Noto Serif TC", serif;
  background:
    radial-gradient(circle at 85% 12%, rgba(180, 83, 9, 0.14), transparent 35%),
    linear-gradient(140deg, var(--bg-a), var(--bg-b));
}
.topbar, .sidepanel {
  border: 2px solid #7c5a37;
  box-shadow: 0 0 0 3px rgba(209, 190, 154, 0.65), 0 14px 28px rgba(120, 88, 56, 0.28);
}
.node {
  border: 2px solid #7c5a37;
  border-radius: 16px;
  box-shadow: inset 0 0 0 1px rgba(255, 250, 236, 0.7), 0 8px 18px rgba(101, 67, 33, 0.22);
}
.link {
  stroke-dasharray: 1 0;
}
"""
    return """
:root {
  --bg-a: #0a1422;
  --bg-b: #0f2439;
  --panel: #11263e;
  --panel-2: #183550;
  --ink: #dbeafe;
  --muted: #9fb7d7;
  --line: #60a5fa;
  --accent: #22d3ee;
  --tier-0: #0ea5e9;
  --tier-1: #14b8a6;
  --tier-2: #f59e0b;
  --tier-3: #ef4444;
}
body {
  font-family: "Barlow Condensed", "Noto Sans TC", sans-serif;
  background:
    linear-gradient(rgba(148,163,184,0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148,163,184,0.08) 1px, transparent 1px),
    linear-gradient(140deg, var(--bg-a), var(--bg-b));
  background-size: 36px 36px, 36px 36px, cover;
}
.topbar, .sidepanel {
  border: 1px solid #3b82f6;
  box-shadow: 0 10px 26px rgba(3, 7, 18, 0.55);
}
.node {
  border: 1px solid #38bdf8;
  border-radius: 10px;
  box-shadow: inset 0 0 0 1px rgba(148, 197, 255, 0.2), 0 8px 20px rgba(7, 25, 49, 0.45);
}
.link {
  stroke-dasharray: 5 3;
}
"""


def variant_titles(kind: str) -> Dict[str, str]:
    if kind == "pixel":
        return {"title": "Poetry Skill Web - Pixel Relic", "subtitle": "RPG / Roguelike Pixel Grid"}
    if kind == "civ":
        return {"title": "Poetry Skill Web - Civilizational Atlas", "subtitle": "Grand Strategy / Civilization Style"}
    if kind == "civ_depth":
        return {"title": "Poetry Skill Web - Civilizational Long Tree", "subtitle": "Depth-first Tech Tree Layout"}
    if kind == "civ_rotated":
        return {"title": "Poetry Skill Web - Civilizational Vertical Tree", "subtitle": "90° Rotated Long-depth Layout"}
    if kind == "civ_rotated_lanes":
        return {
            "title": "Poetry Skill Web - Civilizational Vertical Lanes",
            "subtitle": "90° Rotated Dependency Depth + Theme/Craft Split",
        }
    return {"title": "Poetry Skill Web - Imperial Doctrine", "subtitle": "Paradox-like Doctrine Interface"}


def build_html(data: Dict[str, Any], kind: str, layout_mode: str) -> str:
    titles = variant_titles(kind)
    css_theme = variant_theme_css(kind)
    data_json = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{titles["title"]}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700&family=Cinzel:wght@400;600;700&family=Noto+Sans+TC:wght@400;500;700&family=Noto+Serif+TC:wght@400;600;700&family=Press+Start+2P&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      height: 100%;
      overflow: hidden;
      color: var(--ink);
    }}
    {css_theme}
    .app {{
      height: 100vh;
      padding: 16px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 12px;
      overflow: hidden;
    }}
    .topbar {{
      background: linear-gradient(135deg, var(--panel), var(--panel-2));
      border-radius: 14px;
      padding: 14px;
      display: grid;
      gap: 8px;
      transition: padding .16s ease;
    }}
    .topbar-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}
    .topbar-toggle {{
      border: 1px solid rgba(148, 163, 184, 0.55);
      background: rgba(15, 23, 42, 0.42);
      color: var(--ink);
      border-radius: 9px;
      font-size: 12px;
      padding: 6px 10px;
      cursor: pointer;
    }}
    .topbar-toggle:hover {{
      border-color: rgba(59, 130, 246, 0.72);
    }}
    .topbar.collapsed {{
      padding: 10px 14px;
    }}
    .topbar.collapsed .subtitle,
    .topbar.collapsed .controls {{
      display: none;
    }}
    .topbar h1 {{
      margin: 0;
      font-size: clamp(16px, 2.5vw, 28px);
      letter-spacing: 0.03em;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: clamp(11px, 1.9vw, 14px);
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .controls input[type="search"] {{
      min-width: 220px;
      flex: 1;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.2);
      color: var(--ink);
      border-radius: 8px;
      padding: 10px;
    }}
    .controls input[type="range"] {{ width: 160px; }}
    .layout {{
      min-height: 0;
      height: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 340px;
      gap: 12px;
    }}
    .board {{
      position: relative;
      border-radius: 14px;
      overflow: auto;
      background: rgba(15, 23, 42, 0.18);
      border: 1px solid rgba(148, 163, 184, 0.35);
      min-height: 0;
      height: 100%;
    }}
    .canvas {{
      position: relative;
      transform-origin: top left;
    }}
    .tier-head {{
      position: absolute;
      transform: translate(-50%, -50%);
      background: rgba(0,0,0,0.35);
      border: 1px solid rgba(148, 163, 184, 0.45);
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      white-space: nowrap;
      z-index: 6;
    }}
    .lane-head {{
      position: absolute;
      transform: translate(-50%, -50%);
      background: rgba(0,0,0,0.26);
      border: 1px solid rgba(148, 163, 184, 0.4);
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      white-space: nowrap;
      z-index: 5;
      color: var(--muted);
    }}
    svg.edges {{
      position: absolute;
      inset: 0;
      overflow: visible;
      z-index: 1;
    }}
    .link {{
      fill: none;
      stroke: var(--line);
      stroke-width: 2.2;
      opacity: 0.38;
      transition: opacity .16s ease, stroke-width .16s ease;
    }}
    .link.active {{
      opacity: 0.95;
      stroke-width: 3.1;
    }}
    .node {{
      position: absolute;
      width: 220px;
      padding: 10px;
      background: linear-gradient(145deg, rgba(255,255,255,0.08), rgba(0,0,0,0.18));
      color: var(--ink);
      cursor: pointer;
      z-index: 3;
      transition: transform .14s ease, opacity .14s ease, filter .14s ease;
    }}
    .node:hover {{ transform: translateY(-3px); }}
    .node.dim {{ opacity: 0.23; filter: grayscale(.55); }}
    .node.active {{ transform: translateY(-4px) scale(1.02); filter: brightness(1.08); z-index: 8; }}
    .node .name {{ font-size: 13px; font-weight: 700; line-height: 1.35; }}
    .node .meta {{
      margin-top: 6px;
      font-size: 11px;
      color: var(--muted);
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .node[data-tier="基礎天賦"] {{ border-left: 6px solid var(--tier-0); }}
    .node[data-tier="實驗原型"] {{ border-left: 6px solid var(--tier-1); }}
    .node[data-tier="進階轉職"] {{ border-left: 6px solid var(--tier-2); }}
    .node[data-tier="終極奧義"] {{ border-left: 6px solid var(--tier-3); }}
    .node[data-lane="craft"] {{ border-top: 3px solid #0f766e; }}
    .node[data-lane="hybrid"] {{ border-top: 3px solid #7c3aed; }}
    .node[data-lane="theme"] {{ border-top: 3px solid #b45309; }}
    .sidepanel {{
      background: linear-gradient(170deg, var(--panel), var(--panel-2));
      border-radius: 14px;
      padding: 14px;
      overflow: auto;
      min-height: 0;
      height: 100%;
    }}
    .sidepanel h2 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.35;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      border: 1px solid rgba(255,255,255,0.3);
      margin-top: 8px;
      color: var(--muted);
    }}
    .sec {{ margin-top: 14px; }}
    .sec h3 {{
      margin: 0 0 6px 0;
      font-size: 13px;
      color: var(--accent);
    }}
    .sec p, .sec li {{
      margin: 0;
      font-size: 12px;
      line-height: 1.45;
      color: var(--ink);
    }}
    .sec ul {{
      margin: 0;
      padding-left: 16px;
      display: grid;
      gap: 8px;
    }}
    .relation-group {{
      display: grid;
      gap: 10px;
    }}
    .relation-group h4 {{
      margin: 0 0 4px 0;
      font-size: 12px;
      color: var(--muted);
    }}
    .relation-box {{
      border: 1px solid rgba(148, 163, 184, 0.35);
      border-radius: 8px;
      padding: 6px;
      max-height: 112px;
      overflow: auto;
      background: rgba(0, 0, 0, 0.1);
      font-size: 12px;
      line-height: 1.45;
    }}
    .relation-box code {{
      margin-right: 4px;
      white-space: nowrap;
    }}
    .citation-item {{
      border: 1px solid rgba(148, 163, 184, 0.35);
      border-radius: 10px;
      padding: 8px;
      background: rgba(0, 0, 0, 0.16);
      cursor: help;
    }}
    .citation-item:hover {{
      border-color: rgba(59, 130, 246, 0.65);
    }}
    .citation-tip {{
      margin-top: 4px;
      font-size: 11px;
      color: var(--muted);
    }}
    .citation-preview {{
      position: fixed;
      z-index: 9999;
      width: min(560px, calc(100vw - 24px));
      max-height: min(62vh, 560px);
      overflow: auto;
      padding: 10px;
      border-radius: 10px;
      border: 1px solid rgba(148, 163, 184, 0.65);
      box-shadow: 0 14px 32px rgba(2, 6, 23, 0.55);
      background: rgba(10, 18, 32, 0.95);
      color: #e2e8f0;
      white-space: pre-wrap;
      font-size: 12px;
      line-height: 1.5;
      pointer-events: none;
      user-select: text;
    }}
    .citation-preview.pinned {{
      pointer-events: auto;
    }}
    .citation-preview .hint {{
      margin-top: 10px;
      font-size: 11px;
      color: #93c5fd;
      border-top: 1px solid rgba(148, 163, 184, 0.4);
      padding-top: 6px;
    }}
    .citation-preview .title {{
      font-weight: 700;
      margin-bottom: 6px;
      color: #93c5fd;
    }}
    .muted {{ color: var(--muted); font-size: 12px; }}
    .perf .node {{
      transition: none !important;
      box-shadow: none !important;
      filter: none !important;
    }}
    .perf .link {{
      transition: none !important;
    }}
    .perf .topbar, .perf .sidepanel {{
      box-shadow: none !important;
    }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidepanel {{ min-height: 32vh; height: 38vh; }}
      .board {{ min-height: 0; height: 58vh; }}
      .node {{ width: 196px; }}
      .citation-preview {{
        max-height: 50vh;
        font-size: 11px;
      }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <div class="topbar" id="topbar">
      <div class="topbar-head">
        <h1>{titles["title"]}</h1>
        <button id="toolbarToggle" class="topbar-toggle" type="button">折疊工具列</button>
      </div>
      <div class="subtitle">{titles["subtitle"]}</div>
      <div class="controls">
        <input id="searchBox" type="search" placeholder="搜尋節點名稱 / node_id / 描述關鍵字" />
        <label class="muted">縮放</label>
        <input id="zoomRange" type="range" min="70" max="140" value="100" />
        <label class="muted"><input id="perfToggle" type="checkbox" /> 效能模式</label>
        <span id="stats" class="muted"></span>
      </div>
    </div>

    <div class="layout">
      <div class="board" id="board">
        <div class="canvas" id="canvas">
          <svg class="edges" id="edges"></svg>
        </div>
      </div>
      <aside class="sidepanel" id="panel">
        <h2>選擇一個技能節點</h2>
        <p class="muted">點擊左側節點即可查看描述、前置條件與引文。</p>
      </aside>
    </div>
  </div>
  <div id="citationPreview" class="citation-preview" hidden></div>

  <script>
    const DATA = {data_json};
    const LAYOUT_MODE = "{layout_mode}";
    const tierOrder = DATA.tiers;
    const laneLabels = DATA.lane_labels || {{ craft: "技法進化", hybrid: "交叉進化", theme: "題材進化" }};
    const nodes = [...DATA.nodes];
    const links = [...DATA.links];
    const weakLinksTotal = Number(DATA.weak_links_total || 0);
    const sourceTexts = DATA.source_texts || {{}};
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const prereqByNode = new Map(nodes.map(n => [n.id, new Set(n.prerequisites)]));
    const dependentsByNode = new Map(nodes.map(n => [n.id, new Set()]));
    for (const n of nodes) {{
      for (const p of (n.prerequisites || [])) {{
        if (dependentsByNode.has(p)) dependentsByNode.get(p).add(n.id);
      }}
    }}

    const board = document.getElementById('board');
    const canvas = document.getElementById('canvas');
    const edges = document.getElementById('edges');
    const panel = document.getElementById('panel');
    const topbar = document.getElementById('topbar');
    const toolbarToggle = document.getElementById('toolbarToggle');
    const searchBox = document.getElementById('searchBox');
    const zoomRange = document.getElementById('zoomRange');
    const perfToggle = document.getElementById('perfToggle');
    const stats = document.getElementById('stats');
    const citationPreview = document.getElementById('citationPreview');

    let selectedId = null;
    let positions = new Map();
    let nodeElements = new Map();
    let linkElements = [];
    let activeFocusNodes = new Set();
    let cullingScheduled = false;
    let citationPinned = false;
    let toolbarCollapsed = false;
    const NODE_W = 220;
    const NODE_H = 74;

    function groupedByTier() {{
      const grouped = new Map(tierOrder.map(t => [t, []]));
      for (const n of nodes) {{
        const t = grouped.has(n.tier) ? n.tier : '進階轉職';
        grouped.get(t).push(n);
      }}
      for (const t of tierOrder) {{
        grouped.get(t).sort((a, b) => {{
          if (b.support_count !== a.support_count) return b.support_count - a.support_count;
          return a.name.localeCompare(b.name, 'zh-Hant');
        }});
      }}
      return {{
        keys: [...tierOrder],
        grouped,
        label: (value) => value
      }};
    }}

    function groupedByDepth() {{
      const grouped = new Map();
      for (const n of nodes) {{
        const depth = Number.isFinite(Number(n.depth)) ? Number(n.depth) : 0;
        if (!grouped.has(depth)) grouped.set(depth, []);
        grouped.get(depth).push(n);
      }}
      const keys = [...grouped.keys()].sort((a, b) => a - b);
      for (const key of keys) {{
        grouped.get(key).sort((a, b) => {{
          if (b.support_count !== a.support_count) return b.support_count - a.support_count;
          return a.name.localeCompare(b.name, 'zh-Hant');
        }});
      }}
      return {{
        keys,
        grouped,
        label: (value) => `Depth ${{value}}`
      }};
    }}

    function groupedByStage() {{
      const grouped = new Map();
      for (const n of nodes) {{
        const stage = Number.isFinite(Number(n.stage)) ? Number(n.stage) : 0;
        if (!grouped.has(stage)) grouped.set(stage, []);
        grouped.get(stage).push(n);
      }}
      const keys = [...grouped.keys()].sort((a, b) => a - b);
      for (const key of keys) {{
        grouped.get(key).sort((a, b) => {{
          const aTier = tierOrder.indexOf(a.tier);
          const bTier = tierOrder.indexOf(b.tier);
          if (aTier !== bTier) return aTier - bTier;
          if (b.support_count !== a.support_count) return b.support_count - a.support_count;
          return a.name.localeCompare(b.name, 'zh-Hant');
        }});
      }}
      return {{
        keys,
        grouped,
        label: (value) => `Stage ${{value}}`
      }};
    }}

    function getGrouping() {{
      if (LAYOUT_MODE === 'depth') return groupedByDepth();
      if (LAYOUT_MODE === 'stage' || LAYOUT_MODE === 'stage_rotated' || LAYOUT_MODE === 'stage_rotated_lanes') return groupedByStage();
      return groupedByTier();
    }}

    function setCanvasSize(w, h) {{
      canvas.style.width = `${{w}}px`;
      canvas.style.height = `${{h}}px`;
      edges.setAttribute('width', String(w));
      edges.setAttribute('height', String(h));
      edges.setAttribute('viewBox', `0 0 ${{w}} ${{h}}`);
    }}

    function makeTierHead(x, y, label) {{
      const el = document.createElement('div');
      el.className = 'tier-head';
      el.style.left = `${{x}}px`;
      el.style.top = `${{y}}px`;
      el.textContent = label;
      canvas.appendChild(el);
    }}

    function makeLaneHead(x, y, label) {{
      const el = document.createElement('div');
      el.className = 'lane-head';
      el.style.left = `${{x}}px`;
      el.style.top = `${{y}}px`;
      el.textContent = label;
      canvas.appendChild(el);
    }}

    function renderLayout() {{
      canvas.innerHTML = '';
      canvas.appendChild(edges);
      nodeElements.clear();
      linkElements = [];
      positions.clear();

      const grouping = getGrouping();
      const keys = grouping.keys;
      const grouped = grouping.grouped;
      const maxRows = Math.max(...keys.map(k => grouped.get(k).length), 1);
      const laneMode = LAYOUT_MODE === 'stage_rotated_lanes';
      const rotated = LAYOUT_MODE === 'stage_rotated' || laneMode;
      const verticalFlow = rotated;
      const colGap = (LAYOUT_MODE === 'depth' || LAYOUT_MODE === 'stage' || rotated) ? 250 : 330;
      const rowGap = rotated ? 248 : ((LAYOUT_MODE === 'depth' || LAYOUT_MODE === 'stage') ? 98 : 114);
      const width = rotated
        ? Math.max(1700, maxRows * rowGap + 420)
        : Math.max((LAYOUT_MODE === 'depth' || LAYOUT_MODE === 'stage') ? 2000 : 1400, keys.length * colGap + 380);
      const height = rotated
        ? Math.max(1200, keys.length * colGap + 260)
        : Math.max(860, maxRows * rowGap + 220);
      setCanvasSize(width, height);

      if (verticalFlow) {{
        const viewportW = Math.max(320, board.clientWidth || window.innerWidth || 1200);

        if (laneMode) {{
          const laneOrder = ["craft", "hybrid", "theme"];
          const laneGap = 30;
          const laneInnerGap = 18;
          const laneTargetRows = 4;
          const leftPad = 28;

          const laneBucketsByStage = keys.map((key) => {{
            const arr = grouped.get(key);
            const byLane = new Map(laneOrder.map(lane => [lane, []]));
            for (const node of arr) {{
              const lane = byLane.has(node.lane) ? node.lane : "hybrid";
              byLane.get(lane).push(node);
            }}
            for (const lane of laneOrder) {{
              byLane.get(lane).sort((a, b) => {{
                if (b.support_count !== a.support_count) return b.support_count - a.support_count;
                return a.name.localeCompare(b.name, 'zh-Hant');
              }});
            }}
            return {{ key, byLane }};
          }});

          const laneMaxSubcols = new Map(laneOrder.map(lane => [lane, 1]));
          for (const stageData of laneBucketsByStage) {{
            for (const lane of laneOrder) {{
              const count = stageData.byLane.get(lane).length;
              const neededSubcols = Math.min(4, Math.max(1, Math.ceil(count / laneTargetRows)));
              laneMaxSubcols.set(lane, Math.max(laneMaxSubcols.get(lane) || 1, neededSubcols));
            }}
          }}

          const laneWidths = new Map();
          let totalLaneWidth = 0;
          for (const lane of laneOrder) {{
            const subcols = laneMaxSubcols.get(lane) || 1;
            const widthLane = subcols * NODE_W + (subcols - 1) * laneInnerGap;
            laneWidths.set(lane, widthLane);
            totalLaneWidth += widthLane;
          }}
          totalLaneWidth += laneGap * (laneOrder.length - 1);
          const widthVertical = Math.max(viewportW, leftPad * 2 + totalLaneWidth);

          const laneXStart = new Map();
          let laneCursor = leftPad;
          for (const lane of laneOrder) {{
            laneXStart.set(lane, laneCursor);
            laneCursor += (laneWidths.get(lane) || NODE_W) + laneGap;
          }}

          let yCursor = 106;
          for (const stageData of laneBucketsByStage) {{
            const byLane = stageData.byLane;
            makeTierHead(widthVertical * 0.5, yCursor - 34, `${{grouping.label(stageData.key)}} · 依賴主軸`);
            const stageRowsPerLane = [];

            for (const lane of laneOrder) {{
              const laneNodes = byLane.get(lane);
              const laneWidth = laneWidths.get(lane) || NODE_W;
              const laneX = laneXStart.get(lane) || leftPad;
              const maxSubcols = laneMaxSubcols.get(lane) || 1;
              const subcols = Math.min(maxSubcols, Math.max(1, Math.ceil(laneNodes.length / laneTargetRows)));
              const rows = Math.max(1, Math.ceil(laneNodes.length / subcols));
              stageRowsPerLane.push(rows);

              makeLaneHead(laneX + laneWidth * 0.5, yCursor - 10, laneLabels[lane] || lane);
              const contentWidth = subcols * NODE_W + (subcols - 1) * laneInnerGap;
              const baseX = laneX + Math.max(0, (laneWidth - contentWidth) * 0.5);

              laneNodes.forEach((node, idx) => {{
                const col = Math.floor(idx / rows);
                const row = idx % rows;
                const x = baseX + col * (NODE_W + laneInnerGap);
                const y = yCursor + row * (NODE_H + 18);
                positions.set(node.id, {{ x, y }});
              }});
            }}

            const stageRows = Math.max(...stageRowsPerLane, 1);
            yCursor += stageRows * (NODE_H + 18) + 96;
          }}
          setCanvasSize(widthVertical, Math.max(900, yCursor + 30));
        }} else {{
          const usableW = viewportW - 120;
          const xGap = NODE_W + 24;
          const cols = Math.max(1, Math.floor(usableW / xGap));
          const widthVertical = Math.max(viewportW, 90 + cols * xGap + 60);
          let yCursor = 96;
          keys.forEach((key) => {{
            const arr = grouped.get(key);
            const rows = Math.max(1, Math.ceil(arr.length / cols));
            makeTierHead(widthVertical * 0.5, yCursor - 30, grouping.label(key));
            arr.forEach((node, i) => {{
              const col = i % cols;
              const row = Math.floor(i / cols);
              const x = 70 + col * xGap;
              const y = yCursor + row * (NODE_H + 18);
              positions.set(node.id, {{ x, y }});
            }});
            yCursor += rows * (NODE_H + 18) + 84;
          }});
          setCanvasSize(widthVertical, Math.max(900, yCursor + 30));
        }}
      }} else {{
        keys.forEach((key, idx) => {{
          const x0 = 170 + idx * colGap;
          makeTierHead(x0 + 60, 48, grouping.label(key));
          const arr = grouped.get(key);
          arr.forEach((node, j) => {{
            const x = x0;
            const y = 110 + j * rowGap + ((LAYOUT_MODE === 'depth' || LAYOUT_MODE === 'stage') ? 8 : (idx % 2 === 0 ? 6 : 18));
            positions.set(node.id, {{ x, y }});
          }});
        }});
      }}

      for (const l of links) {{
        const s = positions.get(l.source);
        const t = positions.get(l.target);
        if (!s || !t) continue;
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('class', 'link');
        let x1, y1, x2, y2, cx1, cy1, cx2, cy2;
        if (rotated) {{
          x1 = s.x + NODE_W * 0.5;
          y1 = s.y + NODE_H;
          x2 = t.x + NODE_W * 0.5;
          y2 = t.y;
          const lift = Math.max(30, (y2 - y1) * 0.4);
          cx1 = x1;
          cy1 = y1 + lift;
          cx2 = x2;
          cy2 = y2 - lift;
        }} else {{
          x1 = s.x + NODE_W;
          y1 = s.y + NODE_H * 0.5;
          x2 = t.x;
          y2 = t.y + NODE_H * 0.5;
          const stretch = Math.max(40, (x2 - x1) * 0.38);
          cx1 = x1 + stretch;
          cy1 = y1;
          cx2 = x2 - stretch;
          cy2 = y2;
        }}
        path.setAttribute('d', `M ${{x1}} ${{y1}} C ${{cx1}} ${{cy1}}, ${{cx2}} ${{cy2}}, ${{x2}} ${{y2}}`);
        path.dataset.source = l.source;
        path.dataset.target = l.target;
        edges.appendChild(path);
        linkElements.push(path);
      }}

      for (const n of nodes) {{
        const pos = positions.get(n.id);
        if (!pos) continue;
        const el = document.createElement('div');
        el.className = 'node';
        el.dataset.id = n.id;
        el.dataset.tier = n.tier;
        el.dataset.lane = n.lane || 'hybrid';
        el.style.width = `${{NODE_W}}px`;
        el.style.left = `${{pos.x}}px`;
        el.style.top = `${{pos.y}}px`;
        el.innerHTML = `
          <div class="name">${{n.name || n.id}}</div>
          <div class="meta">
            <span>${{n.tier}}</span>
            <span>${{laneLabels[n.lane] || laneLabels.hybrid}}</span>
            <span>D${{n.depth ?? 0}}</span>
            <span>S${{n.stage ?? 0}}</span>
            <span>support:${{n.support_count}}</span>
            <span>${{n.citations.length}} cite</span>
            <span>weak:${{(n.weak_prerequisites || []).length}}</span>
          </div>
        `;
        el.addEventListener('click', () => selectNode(n.id));
        canvas.appendChild(el);
        nodeElements.set(n.id, el);
      }}

      applySearchFilter();
      updateStats();
      scheduleViewportCulling();
      if (selectedId && nodeMap.has(selectedId)) {{
        selectNode(selectedId);
      }}
    }}

    function escapeHtml(text) {{
      return String(text || '').replace(/[&<>"']/g, s => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',\"'\":'&#39;'}}[s]));
    }}

    function setPerformanceMode(enabled) {{
      document.body.classList.toggle('perf', !!enabled);
      if (perfToggle) perfToggle.checked = !!enabled;
      scheduleViewportCulling();
    }}

    function setToolbarCollapsed(collapsed) {{
      toolbarCollapsed = !!collapsed;
      if (topbar) topbar.classList.toggle('collapsed', toolbarCollapsed);
      if (toolbarToggle) {{
        toolbarToggle.textContent = toolbarCollapsed ? '展開工具列' : '折疊工具列';
      }}
    }}

    function scheduleViewportCulling() {{
      if (cullingScheduled) return;
      cullingScheduled = true;
      requestAnimationFrame(() => {{
        cullingScheduled = false;
        updateViewportCulling();
      }});
    }}

    function updateViewportCulling() {{
      const zoom = Number(zoomRange.value || 100) / 100;
      const left = board.scrollLeft / zoom - 120;
      const top = board.scrollTop / zoom - 120;
      const right = (board.scrollLeft + board.clientWidth) / zoom + 120;
      const bottom = (board.scrollTop + board.clientHeight) / zoom + 120;

      for (const [id, el] of nodeElements.entries()) {{
        if (el.style.display === 'none') {{
          el.style.visibility = 'hidden';
          continue;
        }}
        const p = positions.get(id);
        if (!p) continue;
        const inView = !(p.x + NODE_W < left || p.x > right || p.y + NODE_H < top || p.y > bottom);
        const keep = inView || activeFocusNodes.has(id);
        el.style.visibility = keep ? 'visible' : 'hidden';
      }}

      for (const path of linkElements) {{
        const source = path.dataset.source;
        const target = path.dataset.target;
        if (!source || !target) continue;
        const searchVisiblePair = visibleBySearch.has(source) && visibleBySearch.has(target);
        if (!searchVisiblePair) {{
          path.style.display = 'none';
          continue;
        }}
        const s = positions.get(source);
        const t = positions.get(target);
        if (!s || !t) {{
          path.style.display = 'none';
          continue;
        }}
        const minX = Math.min(s.x, t.x) - 80;
        const maxX = Math.max(s.x + NODE_W, t.x + NODE_W) + 80;
        const minY = Math.min(s.y, t.y) - 80;
        const maxY = Math.max(s.y + NODE_H, t.y + NODE_H) + 80;
        const inView = !(maxX < left || minX > right || maxY < top || minY > bottom);
        const keep = inView || activeFocusNodes.has(source) || activeFocusNodes.has(target);
        path.style.display = keep ? '' : 'none';
      }}
    }}

    function focusOnNodes(nodeIds) {{
      const pts = [...nodeIds]
        .map(id => positions.get(id))
        .filter(Boolean);
      if (!pts.length) return;
      const zoom = Number(zoomRange.value || 100) / 100;
      const minX = Math.min(...pts.map(p => p.x)) - 40;
      const maxX = Math.max(...pts.map(p => p.x + NODE_W)) + 40;
      const minY = Math.min(...pts.map(p => p.y)) - 40;
      const maxY = Math.max(...pts.map(p => p.y + NODE_H)) + 40;
      const cx = ((minX + maxX) * 0.5) * zoom;
      const cy = ((minY + maxY) * 0.5) * zoom;
      const left = Math.max(0, cx - board.clientWidth * 0.5);
      const top = Math.max(0, cy - board.clientHeight * 0.5);
      board.scrollTo({{ left, top, behavior: 'smooth' }});
    }}

    function sortNodeIds(ids) {{
      return [...ids].sort((a, b) => {{
        const nodeA = nodeMap.get(a);
        const nodeB = nodeMap.get(b);
        const stageA = Number(nodeA?.stage ?? 0);
        const stageB = Number(nodeB?.stage ?? 0);
        if (stageA !== stageB) return stageA - stageB;
        const supportA = Number(nodeA?.support_count ?? 0);
        const supportB = Number(nodeB?.support_count ?? 0);
        if (supportB !== supportA) return supportB - supportA;
        return String(a).localeCompare(String(b), 'zh-Hant');
      }});
    }}

    function collectReachable(startId, adjacencyMap) {{
      const visited = new Set();
      const stack = [...(adjacencyMap.get(startId) || [])];
      while (stack.length) {{
        const current = stack.pop();
        if (!current || visited.has(current)) continue;
        visited.add(current);
        for (const nextId of (adjacencyMap.get(current) || [])) {{
          if (!visited.has(nextId)) stack.push(nextId);
        }}
      }}
      return sortNodeIds(visited);
    }}

    function renderNodeRefs(nodeIds) {{
      if (!nodeIds.length) return '（無）';
      return nodeIds.map(id => {{
        const node = nodeMap.get(id);
        const title = node ? `${{id}} · ${{node.name || ''}}` : id;
        return `<code title="${{escapeHtml(title)}}">${{escapeHtml(id)}}</code>`;
      }}).join(' ');
    }}

    function selectNode(nodeId) {{
      selectedId = nodeId;
      hideCitationPreview(true);
      const node = nodeMap.get(nodeId);
      if (!node) return;

      const activeNodes = new Set([nodeId]);
      for (const p of (prereqByNode.get(nodeId) || [])) activeNodes.add(p);
      for (const d of (dependentsByNode.get(nodeId) || [])) activeNodes.add(d);
      activeFocusNodes = activeNodes;

      for (const [id, el] of nodeElements.entries()) {{
        el.classList.toggle('active', id === nodeId);
        el.classList.toggle('dim', !activeNodes.has(id) && searchVisible(id));
      }}

      for (const path of linkElements) {{
        const source = path.dataset.source;
        const target = path.dataset.target;
        const isActive = (target === nodeId) || (source === nodeId);
        path.classList.toggle('active', isActive);
        path.style.opacity = isActive ? '0.98' : '0.12';
      }}

      focusOnNodes(activeNodes);

      const primaryPrereq = node.primary_prerequisites || [];
      const weakPrereq = node.weak_prerequisites || [];
      const downstream = sortNodeIds(dependentsByNode.get(nodeId) || []);
      const upstreamAll = collectReachable(nodeId, prereqByNode);
      const downstreamAll = collectReachable(nodeId, dependentsByNode);
      const sameStageNodes = sortNodeIds(
        nodes.filter(item => Number(item.stage ?? 0) === Number(node.stage ?? 0)).map(item => item.id)
      );
      const midstreamNodes = sameStageNodes.includes(nodeId) ? sameStageNodes : [nodeId, ...sameStageNodes];
      const citations = node.citations || [];
      panel.innerHTML = `
        <h2>${{escapeHtml(node.name || node.id)}}</h2>
        <div class="badge">${{escapeHtml(node.id)}} · ${{escapeHtml(node.tier)}} · ${{escapeHtml(laneLabels[node.lane] || laneLabels.hybrid)}} · Stage ${{node.stage ?? 0}} · Depth ${{node.depth ?? 0}}</div>

        <div class="sec">
          <h3>Unlock Condition</h3>
          <p>${{escapeHtml(node.unlock_condition || '（無）')}}</p>
        </div>
        <div class="sec">
          <h3>Description</h3>
          <p>${{escapeHtml(node.description || '（無）')}}</p>
        </div>
        <div class="sec">
          <h3>Primary Link (drawn)</h3>
          <p>${{primaryPrereq.length ? primaryPrereq.map(p => `<code>${{escapeHtml(p)}}</code>`).join(' / ') : '（無）'}}</p>
        </div>
        <div class="sec">
          <h3>Weak Relations (sidebar only)</h3>
          <p>${{weakPrereq.length ? weakPrereq.map(p => `<code>${{escapeHtml(p)}}</code>`).join(' / ') : '（無）'}}</p>
        </div>
        <div class="sec">
          <h3>Immediate Downstream</h3>
          <p>${{downstream.length ? renderNodeRefs(downstream) : '（無）'}}</p>
        </div>
        <div class="sec">
          <h3>Citations</h3>
          ${{citations.length ? `<ul>${{citations.map(c => `
            <li class="citation-item" data-cite-source="${{encodeURIComponent(c.source_id || '')}}" data-cite-title="${{encodeURIComponent(c.source_title || c.source_id || '')}}">
              <div><strong>${{escapeHtml(c.source_title || c.source_id)}}</strong></div>
              <div class="muted">${{escapeHtml(c.source_id)}}</div>
              <div>「${{escapeHtml(c.quote)}}」</div>
              <div class="muted">${{escapeHtml(c.why)}}</div>
              <div class="citation-tip">滑鼠停留可預覽原詩全文</div>
            </li>
          `).join('')}}</ul>` : '<p>（無）</p>'}}
        </div>
        <div class="sec">
          <h3>Lineage (Full Upstream / Midstream / Downstream)</h3>
          <p class="muted">上游 ${{upstreamAll.length}} · 中游 ${{midstreamNodes.length}} · 下游 ${{downstreamAll.length}}</p>
          <div class="relation-group">
            <div>
              <h4>上游 (All Ancestors)</h4>
              <div class="relation-box">${{renderNodeRefs(upstreamAll)}}</div>
            </div>
            <div>
              <h4>中游 (Same Stage Cluster)</h4>
              <div class="relation-box">${{renderNodeRefs(midstreamNodes)}}</div>
            </div>
            <div>
              <h4>下游 (All Descendants)</h4>
              <div class="relation-box">${{renderNodeRefs(downstreamAll)}}</div>
            </div>
          </div>
        </div>
      `;
      scheduleViewportCulling();
    }}

    function decodeToken(token) {{
      try {{
        return decodeURIComponent(token || "");
      }} catch (err) {{
        return token || "";
      }}
    }}

    function buildCitationPreview(sourceId, sourceTitle, pinned = false) {{
      const poem = sourceTexts[sourceId] || "";
      if (!poem) {{
        return `
          <div class="title">${{escapeHtml(sourceTitle || sourceId)}}</div>
          <div>找不到原詩內容（可在生成命令加入 --poems-root 來載入）。</div>
          ${{pinned ? '<div class="hint">已鎖定：點擊視窗外空白處可關閉。</div>' : ''}}
        `;
      }}
      const clipped = poem.length > 2400 ? `${{poem.slice(0, 2400)}}\n\n...（已截斷）` : poem;
      return `
        <div class="title">${{escapeHtml(sourceTitle || sourceId)}}</div>
        <div>${{escapeHtml(clipped)}}</div>
        ${{pinned ? '<div class="hint">已鎖定：可在此複製文字，點擊視窗外空白處可關閉。</div>' : ''}}
      `;
    }}

    function placeCitationPreview(clientX, clientY) {{
      const padding = 16;
      const rect = citationPreview.getBoundingClientRect();
      let left = clientX + 18;
      let top = clientY + 18;
      if (left + rect.width > window.innerWidth - padding) {{
        left = Math.max(padding, clientX - rect.width - 18);
      }}
      if (top + rect.height > window.innerHeight - padding) {{
        top = Math.max(padding, window.innerHeight - rect.height - padding);
      }}
      citationPreview.style.left = `${{left}}px`;
      citationPreview.style.top = `${{top}}px`;
    }}

    function showCitationPreview(sourceId, sourceTitle, clientX, clientY, pinned = false) {{
      citationPinned = !!pinned;
      citationPreview.classList.toggle('pinned', citationPinned);
      citationPreview.innerHTML = buildCitationPreview(sourceId, sourceTitle, citationPinned);
      citationPreview.hidden = false;
      placeCitationPreview(clientX, clientY);
    }}

    function hideCitationPreview(force = false) {{
      if (citationPinned && !force) return;
      citationPinned = false;
      citationPreview.classList.remove('pinned');
      citationPreview.hidden = true;
      citationPreview.innerHTML = "";
    }}

    let visibleBySearch = new Set(nodes.map(n => n.id));
    function searchVisible(id) {{ return visibleBySearch.has(id); }}

    function applySearchFilter() {{
      const q = (searchBox.value || '').trim().toLowerCase();
      visibleBySearch = new Set();
      hideCitationPreview(true);
      for (const n of nodes) {{
        const hay = `${{n.name}} ${{n.id}} ${{n.description}} ${{n.unlock_condition}} ${{n.tier}}`.toLowerCase();
        const matched = !q || hay.includes(q);
        const el = nodeElements.get(n.id);
        if (el) {{
          el.style.display = matched ? '' : 'none';
          if (matched) visibleBySearch.add(n.id);
        }}
      }}
      for (const path of linkElements) {{
        const s = path.dataset.source;
        const t = path.dataset.target;
        const matched = visibleBySearch.has(s) && visibleBySearch.has(t);
        path.style.display = matched ? '' : 'none';
      }}
      for (const [id, el] of nodeElements.entries()) {{
        el.classList.remove('dim', 'active');
      }}
      for (const path of linkElements) {{
        path.classList.remove('active');
        path.style.opacity = '';
      }}
      if (selectedId && visibleBySearch.has(selectedId)) {{
        selectNode(selectedId);
      }} else {{
        selectedId = null;
        activeFocusNodes = new Set();
      }}
      updateStats();
      scheduleViewportCulling();
    }}

    function updateStats() {{
      const total = nodes.length;
      const visible = visibleBySearch.size;
      stats.textContent = `nodes: ${{visible}} / ${{total}} · strong links: ${{links.length}} · weak links(hidden): ${{weakLinksTotal}}`;
    }}

    function applyZoom() {{
      const v = Number(zoomRange.value || 100) / 100;
      canvas.style.transform = `scale(${{v}})`;
      scheduleViewportCulling();
    }}

    searchBox.addEventListener('input', applySearchFilter);
    zoomRange.addEventListener('input', applyZoom);
    if (perfToggle) {{
      perfToggle.addEventListener('change', () => setPerformanceMode(perfToggle.checked));
    }}
    if (toolbarToggle) {{
      toolbarToggle.addEventListener('click', () => {{
        setToolbarCollapsed(!toolbarCollapsed);
        setTimeout(renderLayout, 0);
      }});
    }}
    board.addEventListener('scroll', scheduleViewportCulling, {{ passive: true }});
    panel.addEventListener('mousemove', (event) => {{
      if (citationPinned) return;
      const rawTarget = event.target;
      if (!(rawTarget instanceof Element)) {{
        hideCitationPreview();
        return;
      }}
      const item = rawTarget.closest('.citation-item');
      if (!item) {{
        hideCitationPreview();
        return;
      }}
      const sourceId = decodeToken(item.dataset.citeSource || "");
      const sourceTitle = decodeToken(item.dataset.citeTitle || sourceId);
      showCitationPreview(sourceId, sourceTitle, event.clientX, event.clientY, false);
    }});
    panel.addEventListener('contextmenu', (event) => {{
      const rawTarget = event.target;
      if (!(rawTarget instanceof Element)) return;
      const item = rawTarget.closest('.citation-item');
      if (!item) return;
      event.preventDefault();
      const sourceId = decodeToken(item.dataset.citeSource || "");
      const sourceTitle = decodeToken(item.dataset.citeTitle || sourceId);
      showCitationPreview(sourceId, sourceTitle, event.clientX, event.clientY, true);
    }});
    panel.addEventListener('mouseleave', () => hideCitationPreview());
    document.addEventListener('pointerdown', (event) => {{
      if (!citationPinned) return;
      const rawTarget = event.target;
      if (rawTarget instanceof Element) {{
        if (citationPreview.contains(rawTarget)) return;
        if (rawTarget.closest('.citation-item')) return;
      }}
      hideCitationPreview(true);
    }});
    window.addEventListener('resize', renderLayout);

    setToolbarCollapsed(false);
    setPerformanceMode(nodes.length > 220 || LAYOUT_MODE === 'stage_rotated' || LAYOUT_MODE === 'stage_rotated_lanes');
    renderLayout();
    applyZoom();
  </script>
</body>
</html>
"""


def write_html(path: Path, html: str) -> None:
    path.write_text(html, encoding="utf-8")


def generate_all(
    master_path: Path,
    out_dir: Path,
    stage_bucket_size: int,
    poems_root: Optional[Path],
    citation_max_chars: int,
) -> None:
    master = load_master(master_path)
    source_texts = build_source_text_map(master, poems_root=poems_root, max_chars=citation_max_chars)
    data = prepare_data(master, stage_bucket_size=stage_bucket_size, source_texts=source_texts)
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("pixel", "tier", "skill_tree_v1_pixel_rpg.html"),
        ("civ", "tier", "skill_tree_v2_civilization.html"),
        ("paradox", "tier", "skill_tree_v3_paradox.html"),
        ("civ_depth", "stage", "skill_tree_v4_civilization_longdepth.html"),
        ("civ_rotated", "stage_rotated", "skill_tree_v5_civilization_rotated.html"),
        ("civ_rotated_lanes", "stage_rotated_lanes", "skill_tree_v6_civilization_rotated_lanes.html"),
    ]
    for kind, layout_mode, filename in variants:
        html = build_html(data, kind, layout_mode)
        write_html(out_dir / filename, html)

    source_label = str(master_path).replace("\\", "/")
    source_label = source_label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    index_html = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Skill Tree Visualizations</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: "Noto Sans TC", sans-serif;
      background: linear-gradient(140deg, #0b1220, #1f2937);
      color: #e5e7eb;
    }
    .panel {
      width: min(760px, 92vw);
      background: rgba(15, 23, 42, 0.75);
      border: 1px solid rgba(148, 163, 184, 0.35);
      border-radius: 16px;
      padding: 20px;
    }
    h1 { margin: 0 0 8px 0; }
    ul { margin: 12px 0 0 0; padding-left: 18px; display: grid; gap: 8px; }
    a { color: #67e8f9; text-decoration: none; }
    a:hover { text-decoration: underline; }
    code { color: #c4b5fd; }
  </style>
</head>
<body>
  <div class="panel">
    <h1>Poetry Skill Tree Visualizations</h1>
    <div>Source: <code>__SOURCE_LABEL__</code></div>
    <p><strong>Note:</strong> V1~V6 are visualization style variants, not pipeline versions (v0.1/v0.2/v0.3.1).</p>
    <ul>
      <li><a href="skill_tree_v1_pixel_rpg.html">V1 - Pixel RPG / Roguelike</a></li>
      <li><a href="skill_tree_v2_civilization.html">V2 - Civilization Style</a></li>
      <li><a href="skill_tree_v3_paradox.html">V3 - Paradox Doctrine Style</a></li>
      <li><a href="skill_tree_v4_civilization_longdepth.html">V4 - Civilization Long Depth</a></li>
      <li><a href="skill_tree_v5_civilization_rotated.html">V5 - Civilization Rotated 90°</a></li>
      <li><a href="skill_tree_v6_civilization_rotated_lanes.html">V6 - Rotated 90° + Theme/Craft Lanes</a></li>
    </ul>
  </div>
</body>
</html>
"""
    index_html = index_html.replace("__SOURCE_LABEL__", source_label)
    write_html(out_dir / "index.html", index_html)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate multiple visualized skill tree HTML variants.")
    parser.add_argument("--master", default=str(DEFAULT_MASTER), help="Path to master_skill_web.json")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output folder for HTML files")
    parser.add_argument("--stage-bucket-size", type=int, default=8, help="Nodes per stage bucket (smaller => deeper tree)")
    parser.add_argument(
        "--poems-root",
        default=str(DEFAULT_POEMS_ROOT) if DEFAULT_POEMS_ROOT else "",
        help="Optional root folder of poem markdown files for citation full-text preview",
    )
    parser.add_argument(
        "--citation-max-chars",
        type=int,
        default=2400,
        help="Maximum characters of each citation source poem embedded in HTML preview",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    poems_root = Path(args.poems_root).expanduser() if args.poems_root else None
    generate_all(
        Path(args.master),
        Path(args.out_dir),
        stage_bucket_size=args.stage_bucket_size,
        poems_root=poems_root,
        citation_max_chars=args.citation_max_chars,
    )

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Set


def build_adjacency(edges: Iterable[dict]) -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    upstream: Dict[str, List[str]] = {}
    downstream: Dict[str, List[str]] = {}
    for edge in edges:
        source_id = str(edge["source_id"])
        target_id = str(edge["target_id"])
        upstream.setdefault(target_id, []).append(source_id)
        downstream.setdefault(source_id, []).append(target_id)
    return upstream, downstream


def walk_ancestors(node_id: str, upstream: Dict[str, List[str]]) -> Set[str]:
    seen: Set[str] = set()
    queue: deque[str] = deque(upstream.get(node_id, []))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        for parent in upstream.get(current, []):
            if parent not in seen:
                queue.append(parent)
    return seen


def walk_descendants(node_id: str, downstream: Dict[str, List[str]]) -> Set[str]:
    seen: Set[str] = set()
    queue: deque[str] = deque(downstream.get(node_id, []))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        for child in downstream.get(current, []):
            if child not in seen:
                queue.append(child)
    return seen


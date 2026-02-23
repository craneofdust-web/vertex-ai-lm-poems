const state = {
  runId: "",
  nodes: [],
  edges: [],
  nodeMap: new Map(),
  positions: new Map(),
  selectedNodeId: "",
  pinnedCitation: null,
};

const laneOrder = ["craft", "hybrid", "theme"];
const laneBaseY = {
  craft: 80,
  hybrid: 360,
  theme: 640,
};

const runIdInput = document.getElementById("run-id-input");
const loadRunBtn = document.getElementById("load-run-btn");
const searchInput = document.getElementById("search-input");
const nodeList = document.getElementById("node-list");
const nodeLayer = document.getElementById("node-layer");
const edgeLayer = document.getElementById("edge-layer");
const graphShell = document.getElementById("graph-shell");
const statusText = document.getElementById("status-text");
const refreshBtn = document.getElementById("refresh-btn");
const smokeBtn = document.getElementById("smoke-btn");
const fullBtn = document.getElementById("full-btn");
const toolbar = document.getElementById("toolbar");
const collapsedBar = document.getElementById("toolbar-collapsed");
const toggleToolbarBtn = document.getElementById("toggle-toolbar-btn");
const expandToolbarBtn = document.getElementById("expand-toolbar-btn");
const citationPreview = document.getElementById("citation-preview");

const detailsEmpty = document.getElementById("details-empty");
const detailsBody = document.getElementById("details-body");
const detailName = document.getElementById("detail-name");
const detailMeta = document.getElementById("detail-meta");
const detailDescription = document.getElementById("detail-description");
const detailUnlock = document.getElementById("detail-unlock");
const detailPrimary = document.getElementById("detail-primary");
const detailWeak = document.getElementById("detail-weak");
const detailDownstream = document.getElementById("detail-downstream");
const lineageUpstream = document.getElementById("lineage-upstream");
const lineageMidstream = document.getElementById("lineage-midstream");
const lineageDownstream = document.getElementById("lineage-downstream");
const detailCitations = document.getElementById("detail-citations");
const pinnedCitation = document.getElementById("pinned-citation");

function setStatus(text) {
  statusText.textContent = text;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && body.detail) detail = String(body.detail);
    } catch (error) {
      // ignore parse errors for non-json responses
    }
    throw new Error(detail);
  }
  return response.json();
}

function buildGraphPath(source, target) {
  const x1 = source.x + 178;
  const y1 = source.y + 36;
  const x2 = target.x;
  const y2 = target.y + 36;
  const c1 = x1 + Math.max(30, (x2 - x1) * 0.42);
  const c2 = x2 - Math.max(30, (x2 - x1) * 0.42);
  return `M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}`;
}

function computeLayout() {
  state.positions.clear();
  const byStage = new Map();
  for (const node of state.nodes) {
    const stage = Number.isFinite(Number(node.stage)) ? Number(node.stage) : 0;
    if (!byStage.has(stage)) byStage.set(stage, []);
    byStage.get(stage).push(node);
  }

  const stages = Array.from(byStage.keys()).sort((a, b) => a - b);
  let maxX = 1400;
  let maxY = 900;

  for (const stage of stages) {
    const x = 70 + stage * 250;
    const bucket = byStage.get(stage) || [];
    const byLane = new Map(laneOrder.map((lane) => [lane, []]));
    for (const node of bucket) {
      const lane = byLane.has(node.lane) ? node.lane : "hybrid";
      byLane.get(lane).push(node);
    }

    for (const lane of laneOrder) {
      const laneNodes = byLane.get(lane) || [];
      laneNodes.sort((a, b) => {
        const stageDiff = Number(a.stage) - Number(b.stage);
        if (stageDiff !== 0) return stageDiff;
        return Number(b.support_count || 0) - Number(a.support_count || 0);
      });
      laneNodes.forEach((node, index) => {
        const y = laneBaseY[lane] + index * 108;
        state.positions.set(node.id, { x, y });
        maxX = Math.max(maxX, x + 280);
        maxY = Math.max(maxY, y + 200);
      });
    }
  }

  nodeLayer.style.width = `${maxX}px`;
  nodeLayer.style.height = `${maxY}px`;
  edgeLayer.setAttribute("width", String(maxX));
  edgeLayer.setAttribute("height", String(maxY));
  edgeLayer.setAttribute("viewBox", `0 0 ${maxX} ${maxY}`);
}

function renderEdges() {
  edgeLayer.innerHTML = "";
  for (const edge of state.edges) {
    const source = state.positions.get(edge.source_id);
    const target = state.positions.get(edge.target_id);
    if (!source || !target) continue;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", buildGraphPath(source, target));
    path.setAttribute("class", "edge-line");
    edgeLayer.appendChild(path);
  }
}

function renderGraphNodes() {
  nodeLayer.innerHTML = "";
  for (const node of state.nodes) {
    const pos = state.positions.get(node.id);
    if (!pos) continue;
    const el = document.createElement("button");
    el.type = "button";
    el.className = "graph-node";
    if (state.selectedNodeId === node.id) el.classList.add("active");
    el.dataset.id = node.id;
    el.dataset.lane = node.lane || "hybrid";
    el.style.left = `${pos.x}px`;
    el.style.top = `${pos.y}px`;

    const title = document.createElement("div");
    title.className = "graph-node-title";
    title.textContent = node.name || node.id;
    el.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "graph-node-meta";
    meta.textContent = `S${node.stage} · ${node.lane} · support ${node.support_count}`;
    el.appendChild(meta);

    el.addEventListener("click", () => selectNode(node.id, true));
    nodeLayer.appendChild(el);
  }
}

function renderNodeList() {
  const keyword = searchInput.value.trim().toLowerCase();
  nodeList.innerHTML = "";
  const filtered = state.nodes.filter((node) => {
    if (!keyword) return true;
    return (
      String(node.id).toLowerCase().includes(keyword) ||
      String(node.name).toLowerCase().includes(keyword)
    );
  });
  for (const node of filtered) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "node-list-item";
    if (state.selectedNodeId === node.id) item.classList.add("active");
    item.dataset.id = node.id;

    const title = document.createElement("div");
    title.textContent = node.name || node.id;
    item.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "node-list-meta";
    meta.textContent = `${node.id} · stage ${node.stage} · ${node.lane}`;
    item.appendChild(meta);

    item.addEventListener("click", () => selectNode(node.id, true));
    nodeList.appendChild(item);
  }
}

function updateSelectionStyles() {
  document.querySelectorAll(".graph-node").forEach((el) => {
    if (el.dataset.id === state.selectedNodeId) {
      el.classList.add("active");
    } else {
      el.classList.remove("active");
    }
  });
  document.querySelectorAll(".node-list-item").forEach((el) => {
    if (el.dataset.id === state.selectedNodeId) {
      el.classList.add("active");
    } else {
      el.classList.remove("active");
    }
  });
}

function centerNode(nodeId) {
  const pos = state.positions.get(nodeId);
  if (!pos) return;
  const targetLeft = Math.max(0, pos.x - graphShell.clientWidth * 0.45);
  const targetTop = Math.max(0, pos.y - graphShell.clientHeight * 0.4);
  graphShell.scrollTo({ left: targetLeft, top: targetTop, behavior: "smooth" });
}

function clearElement(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
}

function addChip(container, node, clickable = true) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chip-link";
  chip.textContent = `${node.name || node.id} (${node.id})`;
  if (clickable) {
    chip.addEventListener("click", () => selectNode(node.id, true));
  }
  container.appendChild(chip);
}

function showCitationPreview(event, text) {
  citationPreview.textContent = text;
  citationPreview.classList.remove("hidden");
  citationPreview.style.left = `${event.clientX + 12}px`;
  citationPreview.style.top = `${event.clientY + 12}px`;
}

function hideCitationPreview() {
  citationPreview.classList.add("hidden");
}

function renderCitations(citations) {
  clearElement(detailCitations);
  if (!citations.length) {
    detailCitations.textContent = "No citations.";
    return;
  }
  for (const citation of citations) {
    const block = document.createElement("div");
    block.className = "citation-item";

    const source = document.createElement("div");
    source.className = "citation-source";
    source.textContent = `${citation.source_title || citation.source_id} (${citation.source_id})`;
    block.appendChild(source);

    const quote = document.createElement("div");
    quote.className = "citation-quote";
    quote.textContent = citation.quote || "(empty quote)";
    block.appendChild(quote);

    const why = document.createElement("div");
    why.className = "citation-why";
    why.textContent = citation.why || "";
    block.appendChild(why);

    const sourceText = String(citation.source_text || "").trim();
    const previewText = sourceText || String(citation.quote || "").trim();
    const pinnedText = previewText || "(source text unavailable)";

    block.addEventListener("mousemove", (event) => {
      if (previewText) showCitationPreview(event, previewText);
    });
    block.addEventListener("mouseleave", hideCitationPreview);
    block.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      state.pinnedCitation = citation;
      pinnedCitation.textContent =
        `${citation.source_title || citation.source_id} (${citation.source_id})\n\n${pinnedText}`;
    });

    detailCitations.appendChild(block);
  }
}

function renderLineageList(container, nodes) {
  clearElement(container);
  if (!nodes.length) {
    container.textContent = "none";
    return;
  }
  for (const node of nodes) {
    addChip(container, node, true);
  }
}

async function renderDetails(nodeData, lineageData) {
  const node = nodeData.node;
  detailsEmpty.classList.add("hidden");
  detailsBody.classList.remove("hidden");

  detailName.textContent = node.name || node.id;
  detailMeta.textContent = `${node.id} · ${node.tier || "unknown"} · stage ${node.stage} · lane ${node.lane}`;
  detailDescription.textContent = node.description || "";
  detailUnlock.textContent = node.unlock_condition ? `unlock: ${node.unlock_condition}` : "";

  clearElement(detailPrimary);
  if (nodeData.primary_link) {
    addChip(detailPrimary, { id: nodeData.primary_link.source_id, name: nodeData.primary_link.source_name }, true);
  } else {
    detailPrimary.textContent = "none";
  }

  clearElement(detailWeak);
  if (nodeData.weak_relations && nodeData.weak_relations.length) {
    nodeData.weak_relations.forEach((item) => {
      addChip(detailWeak, { id: item.source_id, name: item.source_name }, true);
    });
  } else {
    detailWeak.textContent = "none";
  }

  clearElement(detailDownstream);
  if (nodeData.immediate_downstream && nodeData.immediate_downstream.length) {
    nodeData.immediate_downstream.forEach((item) => addChip(detailDownstream, item, true));
  } else {
    detailDownstream.textContent = "none";
  }

  renderLineageList(lineageUpstream, lineageData.lineage.upstream || []);
  renderLineageList(lineageMidstream, lineageData.lineage.midstream || []);
  renderLineageList(lineageDownstream, lineageData.lineage.downstream || []);
  renderCitations(nodeData.citations || []);
}

async function selectNode(nodeId, shouldCenter) {
  if (!nodeId) return;
  state.selectedNodeId = nodeId;
  updateSelectionStyles();
  if (shouldCenter) centerNode(nodeId);
  try {
    setStatus(`loading node ${nodeId}...`);
    const query = state.runId ? `?run_id=${encodeURIComponent(state.runId)}` : "";
    const [nodeData, lineageData] = await Promise.all([
      api(`/node/${encodeURIComponent(nodeId)}${query}`),
      api(`/node/${encodeURIComponent(nodeId)}/lineage${query}`),
    ]);
    await renderDetails(nodeData, lineageData);
    setStatus(`ready · ${state.runId || "latest"}`);
  } catch (error) {
    setStatus(`node load failed: ${error.message}`);
  }
}

async function loadGraph() {
  setStatus("loading graph...");
  const runId = runIdInput.value.trim();
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  try {
    const data = await api(`/graph${query}`);
    state.runId = data.run_id || runId;
    runIdInput.value = state.runId;
    state.nodes = Array.isArray(data.nodes) ? data.nodes : [];
    state.edges = Array.isArray(data.edges) ? data.edges : [];
    state.nodeMap = new Map(state.nodes.map((node) => [node.id, node]));

    computeLayout();
    renderEdges();
    renderGraphNodes();
    renderNodeList();

    if (!state.selectedNodeId || !state.nodeMap.has(state.selectedNodeId)) {
      state.selectedNodeId = state.nodes.length ? state.nodes[0].id : "";
    }
    updateSelectionStyles();
    if (state.selectedNodeId) {
      await selectNode(state.selectedNodeId, false);
    } else {
      setStatus("no nodes found");
    }
  } catch (error) {
    setStatus(`graph load failed: ${error.message}`);
  }
}

async function runPipeline(kind) {
  const endpoint = kind === "full" ? "/run/full" : "/run/smoke";
  const confirmed = window.confirm(
    kind === "full"
      ? "Run full generation pipeline? This can take significant time and cost."
      : "Run smoke test pipeline now?"
  );
  if (!confirmed) return;

  setStatus(`running ${kind}...`);
  try {
    const result = await api(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    let runId = "";
    if (result && result.ingest && result.ingest.run_id) {
      runId = result.ingest.run_id;
    } else if (result && result.pipeline && result.pipeline.run_id) {
      runId = result.pipeline.run_id;
    }
    if (runId) runIdInput.value = runId;
    setStatus(`${kind} completed: ${runId || "ok"}`);
    await loadGraph();
  } catch (error) {
    setStatus(`${kind} failed: ${error.message}`);
  }
}

loadRunBtn.addEventListener("click", () => {
  loadGraph();
});
refreshBtn.addEventListener("click", () => {
  loadGraph();
});
searchInput.addEventListener("input", () => {
  renderNodeList();
});
smokeBtn.addEventListener("click", () => {
  runPipeline("smoke");
});
fullBtn.addEventListener("click", () => {
  runPipeline("full");
});

toggleToolbarBtn.addEventListener("click", () => {
  toolbar.classList.add("hidden");
  collapsedBar.classList.remove("hidden");
});
expandToolbarBtn.addEventListener("click", () => {
  collapsedBar.classList.add("hidden");
  toolbar.classList.remove("hidden");
});

window.addEventListener("resize", () => {
  computeLayout();
  renderEdges();
  renderGraphNodes();
  updateSelectionStyles();
});

loadGraph();

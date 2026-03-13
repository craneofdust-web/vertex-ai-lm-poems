import { api } from "/static/modules/api-client.js";
import { GraphRenderer } from "/static/modules/graph-renderer.js";
import { PanelManager } from "/static/modules/panel-manager.js";

const state = {
  runId: "",
  nodes: [],
  edges: [],
  nodeMap: new Map(),
  positions: new Map(),
  selectedNodeId: "",
  pinnedCitation: null,
  showEdges: true,
  includeWeakEdges: false,
  highlightNodeIds: new Set(),
  highlightEdgeKeys: new Set(),
  leftPanelCollapsed: false,
  leftPanelWidth: 300,
  mobileDrawerOpen: false,
};

const STORAGE_KEY = "poetry-skill-web-ui";

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
const appRoot = document.getElementById("app");
const leftPanel = document.getElementById("left-panel");
const leftPanelResizer = document.getElementById("left-panel-resizer");
const toggleLeftPanelBtn = document.getElementById("toggle-left-panel-btn");
const openLeftDrawerBtn = document.getElementById("open-left-drawer-btn");
const mobileDrawerBackdrop = document.getElementById("mobile-drawer-backdrop");
const toggleEdgesBtn = document.getElementById("toggle-edges-btn");
const includeWeakEdgesInput = document.getElementById("include-weak-edges");
const rightPanel = document.getElementById("right-panel");

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

function isMobileViewport() {
  return window.matchMedia("(max-width: 960px)").matches;
}

function savePreferences() {
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        runId: state.runId,
        showEdges: state.showEdges,
        includeWeakEdges: state.includeWeakEdges,
        leftPanelCollapsed: state.leftPanelCollapsed,
        leftPanelWidth: state.leftPanelWidth,
      })
    );
  } catch (error) {
    console.warn("preference save skipped", error);
  }
}

function loadPreferences() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    state.runId = typeof parsed.runId === "string" ? parsed.runId : state.runId;
    state.showEdges = typeof parsed.showEdges === "boolean" ? parsed.showEdges : state.showEdges;
    state.includeWeakEdges =
      typeof parsed.includeWeakEdges === "boolean" ? parsed.includeWeakEdges : state.includeWeakEdges;
    state.leftPanelCollapsed =
      typeof parsed.leftPanelCollapsed === "boolean"
        ? parsed.leftPanelCollapsed
        : state.leftPanelCollapsed;
    if (Number.isFinite(Number(parsed.leftPanelWidth))) {
      state.leftPanelWidth = Number(parsed.leftPanelWidth);
    }
  } catch (error) {
    console.warn("preference load skipped", error);
  }
}

function renderGraphViewport() {
  graphRenderer.computeLayout();
  graphRenderer.renderEdges();
  graphRenderer.renderGraphNodes();
  graphRenderer.renderNodeList();
  graphRenderer.updateSelectionStyles();
}

function applyLeftPanelWidth() {
  if (!state.leftPanelCollapsed) {
    appRoot.style.setProperty("--left-col-width", `${Math.round(state.leftPanelWidth)}px`);
  }
}

function setLeftPanelWidth(width, persist = true) {
  state.leftPanelWidth = Math.max(232, Math.min(420, Math.round(width)));
  applyLeftPanelWidth();
  renderGraphViewport();
  if (persist) savePreferences();
}

function setMobileDrawerOpen(open) {
  state.mobileDrawerOpen = open;
  appRoot.classList.toggle("drawer-open", open);
  mobileDrawerBackdrop.classList.toggle("hidden", !open);
}

function updateHighlightContext(nodeData, lineageData) {
  const related = new Set([state.selectedNodeId]);
  for (const item of lineageData.lineage.upstream || []) related.add(item.id);
  for (const item of lineageData.lineage.downstream || []) related.add(item.id);
  for (const item of nodeData.weak_relations || []) related.add(item.source_id);
  for (const item of nodeData.immediate_downstream || []) related.add(item.id);
  if (nodeData.primary_link && nodeData.primary_link.source_id) {
    related.add(nodeData.primary_link.source_id);
  }
  state.highlightNodeIds = related;
  const highlightedEdges = new Set();
  for (const edge of state.edges) {
    const touchesSelection =
      edge.source_id === state.selectedNodeId || edge.target_id === state.selectedNodeId;
    const sitsInsideRelated = related.has(edge.source_id) && related.has(edge.target_id);
    if (touchesSelection || sitsInsideRelated) {
      highlightedEdges.add(`${edge.source_id}=>${edge.target_id}`);
    }
  }
  state.highlightEdgeKeys = highlightedEdges;
}

function bindLeftPanelResize() {
  let startX = 0;
  let startWidth = state.leftPanelWidth;

  const onPointerMove = (event) => {
    setLeftPanelWidth(startWidth + event.clientX - startX, false);
  };

  const onPointerUp = () => {
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    document.body.classList.remove("is-resizing");
    savePreferences();
  };

  leftPanelResizer.addEventListener("pointerdown", (event) => {
    if (isMobileViewport() || state.leftPanelCollapsed) return;
    startX = event.clientX;
    startWidth = leftPanel.getBoundingClientRect().width;
    document.body.classList.add("is-resizing");
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  });
}

const graphRenderer = new GraphRenderer({
  state,
  elements: { searchInput, nodeList, nodeLayer, edgeLayer, graphShell },
  onSelectNode: (nodeId, shouldCenter) => selectNode(nodeId, shouldCenter),
});

const panelManager = new PanelManager({
  state,
  elements: {
    citationPreview,
    detailCitations,
    pinnedCitation,
    detailsEmpty,
    detailsBody,
    detailName,
    detailMeta,
    detailDescription,
    detailUnlock,
    detailPrimary,
    detailWeak,
    detailDownstream,
    lineageUpstream,
    lineageMidstream,
    lineageDownstream,
  },
  onSelectNode: (nodeId, shouldCenter) => selectNode(nodeId, shouldCenter),
});

async function selectNode(nodeId, shouldCenter) {
  if (!nodeId) return;
  state.selectedNodeId = nodeId;
  graphRenderer.updateSelectionStyles();
  if (shouldCenter) graphRenderer.centerNode(nodeId);
  try {
    setStatus(`loading node ${nodeId}...`);
    const query = state.runId ? `?run_id=${encodeURIComponent(state.runId)}` : "";
    const [nodeData, lineageData] = await Promise.all([
      api(`/node/${encodeURIComponent(nodeId)}${query}`),
      api(`/node/${encodeURIComponent(nodeId)}/lineage${query}`),
    ]);
    panelManager.renderDetails(nodeData, lineageData);
    updateHighlightContext(nodeData, lineageData);
    graphRenderer.renderEdges();
    graphRenderer.updateSelectionStyles();
    if (isMobileViewport()) setMobileDrawerOpen(false);
    setStatus(`ready · ${state.runId || "latest"}`);
  } catch (error) {
    setStatus(`node load failed: ${error.message}`);
  }
}

async function loadGraph() {
  setStatus("loading graph...");
  const runId = runIdInput.value.trim();
  const params = new URLSearchParams();
  if (runId) params.set("run_id", runId);
  if (state.includeWeakEdges) params.set("include_weak", "true");
  const query = params.toString() ? `?${params.toString()}` : "";
  try {
    const data = await api(`/graph${query}`);
    state.runId = data.run_id || runId;
    runIdInput.value = state.runId;
    state.nodes = Array.isArray(data.nodes) ? data.nodes : [];
    state.edges = Array.isArray(data.edges) ? data.edges : [];
    state.nodeMap = new Map(state.nodes.map((node) => [node.id, node]));
    state.highlightNodeIds = new Set();
    state.highlightEdgeKeys = new Set();

    renderGraphViewport();

    if (!state.selectedNodeId || !state.nodeMap.has(state.selectedNodeId)) {
      state.selectedNodeId = state.nodes.length ? state.nodes[0].id : "";
    }
    if (state.selectedNodeId) {
      await selectNode(state.selectedNodeId, false);
    } else {
      setStatus("no nodes found");
    }
    savePreferences();
  } catch (error) {
    setStatus(`graph load failed: ${error.message}`);
  }
}

function updateEdgeControls() {
  toggleEdgesBtn.textContent = state.showEdges ? "Hide Lines" : "Show Lines";
  includeWeakEdgesInput.checked = state.includeWeakEdges;
}

function setLeftPanelCollapsed(collapsed, persist = true) {
  state.leftPanelCollapsed = collapsed;
  leftPanel.classList.toggle("collapsed", collapsed);
  appRoot.classList.toggle("left-collapsed", collapsed);
  toggleLeftPanelBtn.textContent = collapsed ? "Expand" : "Collapse";
  applyLeftPanelWidth();
  if (persist) savePreferences();
  renderGraphViewport();
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
  graphRenderer.renderNodeList();
});
smokeBtn.addEventListener("click", () => {
  runPipeline("smoke");
});
fullBtn.addEventListener("click", () => {
  runPipeline("full");
});
toggleLeftPanelBtn.addEventListener("click", () => {
  if (isMobileViewport()) {
    setMobileDrawerOpen(false);
    return;
  }
  const next = !leftPanel.classList.contains("collapsed");
  setLeftPanelCollapsed(next);
});
openLeftDrawerBtn.addEventListener("click", () => {
  setMobileDrawerOpen(true);
});
mobileDrawerBackdrop.addEventListener("click", () => {
  setMobileDrawerOpen(false);
});
toggleEdgesBtn.addEventListener("click", () => {
  state.showEdges = !state.showEdges;
  updateEdgeControls();
  graphRenderer.renderEdges();
  savePreferences();
});
includeWeakEdgesInput.addEventListener("change", () => {
  state.includeWeakEdges = includeWeakEdgesInput.checked;
  updateEdgeControls();
  savePreferences();
  loadGraph();
});
rightPanel.addEventListener("scroll", panelManager.hideCitationPreview);
graphShell.addEventListener("scroll", panelManager.hideCitationPreview);

toggleToolbarBtn.addEventListener("click", () => {
  toolbar.classList.add("hidden");
  collapsedBar.classList.remove("hidden");
});
expandToolbarBtn.addEventListener("click", () => {
  collapsedBar.classList.add("hidden");
  toolbar.classList.remove("hidden");
});

window.addEventListener("resize", () => {
  panelManager.hideCitationPreview();
  if (!isMobileViewport()) setMobileDrawerOpen(false);
  renderGraphViewport();
});

loadPreferences();
runIdInput.value = state.runId;
applyLeftPanelWidth();
setLeftPanelCollapsed(state.leftPanelCollapsed, false);
updateEdgeControls();
bindLeftPanelResize();
loadGraph();

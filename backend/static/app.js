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
const appRoot = document.getElementById("app");
const leftPanel = document.getElementById("left-panel");
const toggleLeftPanelBtn = document.getElementById("toggle-left-panel-btn");
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

    graphRenderer.computeLayout();
    graphRenderer.renderEdges();
    graphRenderer.renderGraphNodes();
    graphRenderer.renderNodeList();

    if (!state.selectedNodeId || !state.nodeMap.has(state.selectedNodeId)) {
      state.selectedNodeId = state.nodes.length ? state.nodes[0].id : "";
    }
    graphRenderer.updateSelectionStyles();
    if (state.selectedNodeId) {
      await selectNode(state.selectedNodeId, false);
    } else {
      setStatus("no nodes found");
    }
  } catch (error) {
    setStatus(`graph load failed: ${error.message}`);
  }
}

function updateEdgeControls() {
  toggleEdgesBtn.textContent = state.showEdges ? "Hide Lines" : "Show Lines";
  includeWeakEdgesInput.checked = state.includeWeakEdges;
}

function setLeftPanelCollapsed(collapsed) {
  leftPanel.classList.toggle("collapsed", collapsed);
  appRoot.classList.toggle("left-collapsed", collapsed);
  toggleLeftPanelBtn.textContent = collapsed ? "Expand" : "Collapse";
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
  const next = !leftPanel.classList.contains("collapsed");
  setLeftPanelCollapsed(next);
});
toggleEdgesBtn.addEventListener("click", () => {
  state.showEdges = !state.showEdges;
  updateEdgeControls();
  graphRenderer.renderEdges();
});
includeWeakEdgesInput.addEventListener("change", () => {
  state.includeWeakEdges = includeWeakEdgesInput.checked;
  updateEdgeControls();
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
  graphRenderer.computeLayout();
  graphRenderer.renderEdges();
  graphRenderer.renderGraphNodes();
  graphRenderer.updateSelectionStyles();
});

updateEdgeControls();
loadGraph();

const laneOrder = ["craft", "hybrid", "theme"];
const NODE_CARD_WIDTH = 186;
const NODE_CARD_HEIGHT = 96;
const STAGE_X_STEP = 270;
const NODE_Y_STEP = 126;
const LANE_BLOCK_GAP = 80;
const GRAPH_TOP_PADDING = 80;
const GRAPH_LEFT_PADDING = 70;

export class GraphRenderer {
  constructor({ state, elements, onSelectNode }) {
    this.state = state;
    this.elements = elements;
    this.onSelectNode = onSelectNode;
  }

  buildGraphPath(source, target) {
    const x1 = source.x + NODE_CARD_WIDTH;
    const y1 = source.y + NODE_CARD_HEIGHT / 2;
    const x2 = target.x;
    const y2 = target.y + NODE_CARD_HEIGHT / 2;
    const c1 = x1 + Math.max(30, (x2 - x1) * 0.42);
    const c2 = x2 - Math.max(30, (x2 - x1) * 0.42);
    return `M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}`;
  }

  computeLaneBaseY(byStage) {
    const laneMaxCount = new Map(laneOrder.map((lane) => [lane, 0]));
    for (const bucket of byStage.values()) {
      const counts = new Map(laneOrder.map((lane) => [lane, 0]));
      for (const node of bucket) {
        const lane = counts.has(node.lane) ? node.lane : "hybrid";
        counts.set(lane, Number(counts.get(lane) || 0) + 1);
      }
      for (const lane of laneOrder) {
        laneMaxCount.set(
          lane,
          Math.max(Number(laneMaxCount.get(lane) || 0), Number(counts.get(lane) || 0))
        );
      }
    }

    const base = {};
    let cursorY = GRAPH_TOP_PADDING;
    for (const lane of laneOrder) {
      base[lane] = cursorY;
      const count = Math.max(1, Number(laneMaxCount.get(lane) || 0));
      cursorY += count * NODE_Y_STEP + LANE_BLOCK_GAP;
    }
    return base;
  }

  computeLayout() {
    const { state } = this;
    const { nodeLayer, edgeLayer } = this.elements;

    state.positions.clear();
    const byStage = new Map();
    for (const node of state.nodes) {
      const stage = Number.isFinite(Number(node.stage)) ? Number(node.stage) : 0;
      if (!byStage.has(stage)) byStage.set(stage, []);
      byStage.get(stage).push(node);
    }

    const stages = Array.from(byStage.keys()).sort((a, b) => a - b);
    const laneBaseY = this.computeLaneBaseY(byStage);
    let maxX = 1400;
    let maxY = 900;

    for (const stage of stages) {
      const x = GRAPH_LEFT_PADDING + stage * STAGE_X_STEP;
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
          const y = Number(laneBaseY[lane]) + index * NODE_Y_STEP;
          state.positions.set(node.id, { x, y });
          maxX = Math.max(maxX, x + NODE_CARD_WIDTH + 120);
          maxY = Math.max(maxY, y + NODE_CARD_HEIGHT + 120);
        });
      }
    }

    nodeLayer.style.width = `${maxX}px`;
    nodeLayer.style.height = `${maxY}px`;
    edgeLayer.style.width = `${maxX}px`;
    edgeLayer.style.height = `${maxY}px`;
    edgeLayer.setAttribute("width", String(maxX));
    edgeLayer.setAttribute("height", String(maxY));
    edgeLayer.setAttribute("viewBox", `0 0 ${maxX} ${maxY}`);
  }

  renderEdges() {
    const { state } = this;
    const { edgeLayer } = this.elements;

    edgeLayer.innerHTML = "";
    if (!state.showEdges) return;
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
      <marker id="edge-arrow-primary" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="strokeWidth">
        <path d="M 0 0 L 10 5 L 0 10 z" class="edge-arrow edge-arrow-primary"></path>
      </marker>
      <marker id="edge-arrow-secondary" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto" markerUnits="strokeWidth">
        <path d="M 0 0 L 9 4.5 L 0 9 z" class="edge-arrow edge-arrow-secondary"></path>
      </marker>
    `;
    edgeLayer.appendChild(defs);
    for (const edge of state.edges) {
      const source = state.positions.get(edge.source_id);
      const target = state.positions.get(edge.target_id);
      if (!source || !target) continue;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", this.buildGraphPath(source, target));
      const classNames = ["edge-line"];
      const edgeKey = `${edge.source_id}=>${edge.target_id}`;
      const isPrimary = String(edge.edge_type || "") === "primary";
      const isHighlighted = state.highlightEdgeKeys && state.highlightEdgeKeys.has(edgeKey);
      if (!isPrimary) classNames.push("edge-weak");
      if (Number(edge.is_direct || 0) !== 1) classNames.push("edge-far");
      if (isPrimary) classNames.push("edge-primary");
      if (state.selectedNodeId) {
        classNames.push(isHighlighted ? "edge-highlighted" : "edge-muted");
      }
      path.setAttribute("class", classNames.join(" "));
      path.setAttribute("marker-end", isPrimary ? "url(#edge-arrow-primary)" : "url(#edge-arrow-secondary)");
      edgeLayer.appendChild(path);
    }
  }

  renderGraphNodes() {
    const { state } = this;
    const { nodeLayer } = this.elements;

    nodeLayer.innerHTML = "";
    for (const node of state.nodes) {
      const pos = state.positions.get(node.id);
      if (!pos) continue;
      const el = document.createElement("button");
      el.type = "button";
      el.className = "graph-node";
      if (state.selectedNodeId === node.id) el.classList.add("active");
      if (state.highlightNodeIds && state.highlightNodeIds.has(node.id)) el.classList.add("related");
      el.dataset.id = node.id;
      el.dataset.lane = node.lane || "hybrid";
      el.style.left = `${pos.x}px`;
      el.style.top = `${pos.y}px`;

      const badges = document.createElement("div");
      badges.className = "graph-node-badges";

      const stageBadge = document.createElement("span");
      stageBadge.className = "graph-node-badge graph-node-badge-stage";
      stageBadge.textContent = `S${node.stage}`;
      badges.appendChild(stageBadge);

      const laneBadge = document.createElement("span");
      laneBadge.className = "graph-node-badge graph-node-badge-lane";
      laneBadge.textContent = node.lane || "hybrid";
      badges.appendChild(laneBadge);

      const supportBadge = document.createElement("span");
      supportBadge.className = "graph-node-badge graph-node-badge-support";
      supportBadge.textContent = `support ${node.support_count}`;
      badges.appendChild(supportBadge);

      el.appendChild(badges);

      const title = document.createElement("div");
      title.className = "graph-node-title";
      title.textContent = node.name || node.id;
      el.appendChild(title);

      const meta = document.createElement("div");
      meta.className = "graph-node-meta";
      meta.textContent = `${node.id} · ${node.tier || "tier?"}`;
      el.appendChild(meta);

      el.addEventListener("click", () => this.onSelectNode(node.id, true));
      nodeLayer.appendChild(el);
    }
  }

  renderNodeList() {
    const { state } = this;
    const { searchInput, nodeList } = this.elements;

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
      if (state.highlightNodeIds && state.highlightNodeIds.has(node.id)) item.classList.add("related");
      item.dataset.id = node.id;

      const title = document.createElement("div");
      title.textContent = node.name || node.id;
      item.appendChild(title);

      const meta = document.createElement("div");
      meta.className = "node-list-meta";
      meta.textContent = `${node.id} · stage ${node.stage} · ${node.lane}`;
      item.appendChild(meta);

      item.addEventListener("click", () => this.onSelectNode(node.id, true));
      nodeList.appendChild(item);
    }
  }

  updateSelectionStyles() {
    const { state } = this;
    document.querySelectorAll(".graph-node").forEach((el) => {
      if (el.dataset.id === state.selectedNodeId) {
        el.classList.add("active");
      } else {
        el.classList.remove("active");
      }
      if (state.highlightNodeIds && state.highlightNodeIds.has(el.dataset.id)) {
        el.classList.add("related");
      } else {
        el.classList.remove("related");
      }
    });
    document.querySelectorAll(".node-list-item").forEach((el) => {
      if (el.dataset.id === state.selectedNodeId) {
        el.classList.add("active");
      } else {
        el.classList.remove("active");
      }
      if (state.highlightNodeIds && state.highlightNodeIds.has(el.dataset.id)) {
        el.classList.add("related");
      } else {
        el.classList.remove("related");
      }
    });
  }

  centerNode(nodeId) {
    const { state } = this;
    const { graphShell } = this.elements;

    const pos = state.positions.get(nodeId);
    if (!pos) return;
    const targetLeft = Math.max(0, pos.x - graphShell.clientWidth * 0.45);
    const targetTop = Math.max(0, pos.y - graphShell.clientHeight * 0.4);
    graphShell.scrollTo({ left: targetLeft, top: targetTop, behavior: "smooth" });
  }
}

export class PanelManager {
  constructor({ state, elements, onSelectNode }) {
    this.state = state;
    this.elements = elements;
    this.onSelectNode = onSelectNode;
  }

  clearElement(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  addChip(container, node, clickable = true) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip-link";
    chip.textContent = `${node.name || node.id} (${node.id})`;
    if (clickable) {
      chip.addEventListener("click", () => this.onSelectNode(node.id, true));
    }
    container.appendChild(chip);
  }

  showCitationPreview(anchorElement, text) {
    const { citationPreview } = this.elements;
    if (!text) return;
    citationPreview.textContent = text;
    citationPreview.classList.remove("hidden");
    const margin = 12;
    const anchorRect = anchorElement.getBoundingClientRect();
    const previewRect = citationPreview.getBoundingClientRect();

    let left = anchorRect.left - previewRect.width - margin;
    if (left < 8) {
      left = anchorRect.right + margin;
    }
    if (left + previewRect.width > window.innerWidth - 8) {
      left = Math.max(8, window.innerWidth - previewRect.width - 8);
    }

    let top = anchorRect.top;
    if (top + previewRect.height > window.innerHeight - 8) {
      top = window.innerHeight - previewRect.height - 8;
    }
    if (top < 8) {
      top = 8;
    }

    citationPreview.style.left = `${Math.round(left)}px`;
    citationPreview.style.top = `${Math.round(top)}px`;
  }

  hideCitationPreview = () => {
    this.elements.citationPreview.classList.add("hidden");
  };

  renderCitations(citations) {
    const { detailCitations, pinnedCitation } = this.elements;

    this.clearElement(detailCitations);
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

      block.addEventListener("mouseenter", () => {
        if (previewText) this.showCitationPreview(block, previewText);
      });
      block.addEventListener("focusin", () => {
        if (previewText) this.showCitationPreview(block, previewText);
      });
      block.addEventListener("mouseleave", this.hideCitationPreview);
      block.addEventListener("focusout", this.hideCitationPreview);
      block.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        this.state.pinnedCitation = citation;
        pinnedCitation.textContent =
          `${citation.source_title || citation.source_id} (${citation.source_id})\n\n${pinnedText}`;
      });

      detailCitations.appendChild(block);
    }
  }

  renderLineageList(container, nodes) {
    this.clearElement(container);
    if (!nodes.length) {
      container.textContent = "none";
      return;
    }
    for (const node of nodes) {
      this.addChip(container, node, true);
    }
  }

  renderDetails(nodeData, lineageData) {
    const {
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
    } = this.elements;

    const node = nodeData.node;
    detailsEmpty.classList.add("hidden");
    detailsBody.classList.remove("hidden");

    detailName.textContent = node.name || node.id;
    detailMeta.textContent = `${node.id} · ${node.tier || "unknown"} · stage ${node.stage} · lane ${node.lane}`;
    detailDescription.textContent = node.description || "";
    detailUnlock.textContent = node.unlock_condition ? `unlock: ${node.unlock_condition}` : "";

    this.clearElement(detailPrimary);
    if (nodeData.primary_link) {
      this.addChip(
        detailPrimary,
        { id: nodeData.primary_link.source_id, name: nodeData.primary_link.source_name },
        true
      );
    } else {
      detailPrimary.textContent = "none";
    }

    this.clearElement(detailWeak);
    if (nodeData.weak_relations && nodeData.weak_relations.length) {
      nodeData.weak_relations.forEach((item) => {
        this.addChip(detailWeak, { id: item.source_id, name: item.source_name }, true);
      });
    } else {
      detailWeak.textContent = "none";
    }

    this.clearElement(detailDownstream);
    if (nodeData.immediate_downstream && nodeData.immediate_downstream.length) {
      nodeData.immediate_downstream.forEach((item) => this.addChip(detailDownstream, item, true));
    } else {
      detailDownstream.textContent = "none";
    }

    this.renderLineageList(lineageUpstream, lineageData.lineage.upstream || []);
    this.renderLineageList(lineageMidstream, lineageData.lineage.midstream || []);
    this.renderLineageList(lineageDownstream, lineageData.lineage.downstream || []);
    this.renderCitations(nodeData.citations || []);
  }
}

// Strata workbench graph page: draws the focus neighbourhood with the vendored Cytoscape + dagre.
//
// Progressive enhancement only. The server renders the neighbourhood as a list of links
// (data-graph-list); this file fetches the same neighbourhood as JSON from /api/graph (the
// URL is in data-src, never inline JSON) and, once it draws, hides the list. Colours, captions
// and paths all arrive in the JSON (workbench/graph.py); nothing here derives a status. Theme
// colours are read from the page's CSS custom properties and re-read when the theme flips.
//
// Safety: no HTML string is ever parsed; labels reach the canvas as Cytoscape data only.
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;
  var canvas = doc.querySelector("[data-graph-canvas]");
  var list = doc.querySelector("[data-graph-list]");
  if (!canvas || typeof window.cytoscape !== "function") return; // the list stays

  try {
    if (typeof window.cytoscapeDagre !== "undefined") window.cytoscape.use(window.cytoscapeDagre);
  } catch (_) { /* already registered */ }

  var LABEL_MAX = 34;

  function token(name) { return getComputedStyle(root).getPropertyValue(name).trim(); }

  function shorten(text) {
    text = String(text);
    return text.length > LABEL_MAX ? text.slice(0, LABEL_MAX - 1) + "…" : text;
  }

  function style() {
    var surface = token("--surface2"), focus = token("--surface3"), text = token("--text");
    var muted = token("--muted"), ring = token("--focus"), font = token("--mono");
    return [
      {
        selector: "node",
        style: {
          shape: "round-rectangle",
          width: 260,
          height: 44,
          "background-color": surface,
          "border-width": 1.5,
          "border-color": "data(color)",
          label: "data(text)",
          "text-wrap": "wrap",
          "text-valign": "center",
          "text-halign": "center",
          color: text,
          "font-family": font,
          "font-size": 11.5,
          "line-height": 1.35,
        },
      },
      { selector: "node[kind = 'pdt']", style: { shape: "cut-rectangle" } },
      { selector: "node[kind = 'physical_table']", style: { shape: "rectangle" } },
      { selector: "node[?focus]", style: { "background-color": focus, "border-width": 3 } },
      { selector: "node:active, node:selected", style: { "overlay-opacity": 0, "border-color": ring } },
      {
        selector: "edge",
        style: {
          width: 1.4,
          "line-color": "data(color)",
          "target-arrow-color": "data(color)",
          "target-arrow-shape": "triangle",
          "arrow-scale": 0.8,
          "curve-style": "bezier",
        },
      },
      { selector: "edge[relation = 'explore→joined_view']", style: { "line-style": "dashed" } },
      { selector: ".dim", style: { opacity: 0.35 } },
      { selector: "core", style: { "active-bg-color": muted } },
    ];
  }

  function draw(data) {
    var elements = data.nodes.map(function (n) {
      n.data.text = shorten(n.data.display_label) + "\n" + n.data.caption;
      return n;
    }).concat(data.edges);
    canvas.hidden = false;
    var cy = window.cytoscape({
      container: canvas,
      elements: elements,
      style: style(),
      wheelSensitivity: 0.3,
      boxSelectionEnabled: false,
      autoungrabify: true,
      layout: { name: "dagre", rankDir: "LR", nodeSep: 14, rankSep: 90, fit: true, padding: 24 },
    });
    cy.on("tap", "node", function (e) {
      var path = e.target.data("path");
      if (path) location.href = path;
    });
    cy.on("mouseover", "node", function (e) {
      canvas.style.cursor = e.target.data("path") ? "pointer" : "default";
      cy.elements().addClass("dim");
      e.target.closedNeighborhood().removeClass("dim");
    });
    cy.on("mouseout", "node", function () {
      canvas.style.cursor = "default";
      cy.elements().removeClass("dim");
    });
    // The theme toggle flips data-theme on <html>: restyle from the new tokens.
    new MutationObserver(function () { cy.style(style()); }).observe(root, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    if (list) list.hidden = true;
  }

  fetch(canvas.getAttribute("data-src"), { credentials: "same-origin" })
    .then(function (r) {
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    })
    .then(draw)
    .catch(function () { canvas.hidden = true; }); // the server-rendered list stays

  // Esc goes back (the keyboard map's "Esc back"), unless a dialog or a field has it.
  doc.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || e.defaultPrevented) return;
    if (doc.querySelector("dialog[open]")) return;
    if (e.target.closest && e.target.closest("input, textarea, select")) return;
    history.back();
  });
})();

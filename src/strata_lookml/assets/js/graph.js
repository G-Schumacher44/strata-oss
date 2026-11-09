// Strata workbench graph page: draws the focus neighbourhood with the vendored Cytoscape + dagre.
//
// Progressive enhancement only. The server renders the neighbourhood as a list of links
// (data-graph-list); this file fetches the same neighbourhood as JSON from /api/graph (the
// URL is in data-src, never inline JSON) and, once it draws, hides the list. Colours, captions
// and paths all arrive in the JSON (workbench/graph.py); nothing here derives a status. Theme
// colours are read from the page's CSS custom properties and re-read when the theme flips.
//
// In the static export there is no /api/graph: the whole graph is embedded once
// (window.StrataExport.data.graph) and `neighbourhood` below cuts the focus out of it, the
// same walk as workbench/graph.py (tests compare the two). router.js fires `strata:page` when
// it shows another page, and the drawing starts over (`init`).
//
// Safety: no HTML string is ever parsed; labels reach the canvas as Cytoscape data only.
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;
  var cy = null;
  var observer = null;

  // <neighbourhood> workbench/graph.py `neighbourhood` over export_graph_data(): nodes come
  // sorted by id, so a ring is ordered by position (tests run both and compare).
  function neighbourhood(data, focus, up, down, siblings, cap) {
    var nodes = Object.create(null), rank = Object.create(null);
    data.nodes.forEach(function (n, i) { nodes[n.id] = n; rank[n.id] = i; });
    if (!(focus in nodes)) return null;
    var outEdges = Object.create(null), inEdges = Object.create(null);
    data.edges.forEach(function (e) {
      (outEdges[e.source] = outEdges[e.source] || []).push(e.target);
      (inEdges[e.target] = inEdges[e.target] || []).push(e.source);
    });
    var ring = Object.create(null);
    ring[focus] = "focus";
    var order = [focus];
    function reach(frontier, step) {
      var seen = Object.create(null), found = [];
      frontier.forEach(function (f) {
        (step[f] || []).forEach(function (n) { if (!seen[n]) { seen[n] = true; found.push(n); } });
      });
      return found;
    }
    function unringed(ids) { return ids.filter(function (n) { return !(n in ring); }); }
    function byRank(a, b) { return rank[a] - rank[b]; }
    var upFrontier = [focus], downFrontier = [focus];
    for (var hop = 1; hop <= Math.max(up, down); hop++) {
      var found = [];
      if (hop <= up) {
        upFrontier = unringed(reach(upFrontier, outEdges));
        found.push(["upstream " + hop, upFrontier]);
      }
      if (hop <= down) {
        downFrontier = unringed(reach(downFrontier, inEdges));
        found.push(["downstream " + hop, downFrontier]);
      }
      found.forEach(function (f) {
        unringed(f[1]).sort(byRank).forEach(function (id) { ring[id] = f[0]; order.push(id); });
      });
    }
    if (siblings) {
      unringed(reach(inEdges[focus] || [], outEdges)).sort(byRank).forEach(function (id) {
        ring[id] = "siblings";
        order.push(id);
      });
    }
    var kept = order.slice(0, Math.max(1, cap));
    var keep = Object.create(null);
    kept.forEach(function (id) { keep[id] = true; });
    return {
      focus: focus,
      up: up,
      down: down,
      siblings: siblings,
      total: order.length,
      shown: kept.length,
      nodes: kept.map(function (id) {
        return { data: Object.assign({}, nodes[id], { ring: ring[id], focus: id === focus }) };
      }),
      edges: data.edges
        .filter(function (e) { return keep[e.source] && keep[e.target]; })
        .map(function (e) { return { data: Object.assign({}, e) }; }),
    };
  }
  // </neighbourhood>

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

  function draw(canvas, list, data) {
    var elements = data.nodes.map(function (n) {
      n.data.text = shorten(n.data.display_label) + "\n" + n.data.caption;
      return n;
    }).concat(data.edges);
    canvas.hidden = false;
    cy = window.cytoscape({
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
      if (!path) return;
      if (window.StrataExport) window.StrataExport.go(path);
      else location.href = path;
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
    observer = new MutationObserver(function () { if (cy) cy.style(style()); });
    observer.observe(root, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    if (list) list.hidden = true;
  }

  // A hop state the export did not pre-render: the server's cap note went with its list.
  function capNote(section, hood) {
    if (!section || !section.hasAttribute("data-variant") || hood.shown >= hood.total) return;
    var note = doc.createElement("p");
    note.className = "gnote";
    note.setAttribute("role", "status");
    note.textContent = "Showing " + hood.shown + " of " + hood.total + " nodes (capped at " +
      window.StrataExport.data.cap + "). Use 1 hop or turn siblings off to see the rest.";
    section.insertBefore(note, section.querySelector("[data-graph-canvas]"));
  }

  function init() {
    if (observer) { observer.disconnect(); observer = null; }
    if (cy) { cy.destroy(); cy = null; }
    var canvas = doc.querySelector("[data-graph-canvas]");
    var list = doc.querySelector("[data-graph-list]");
    if (!canvas || typeof window.cytoscape !== "function") return; // the list stays
    if (window.StrataExport) {
      var section = canvas.closest("[data-graph]");
      var hood = neighbourhood(
        window.StrataExport.data.graph,
        section.getAttribute("data-focus"),
        Number(section.getAttribute("data-up")),
        Number(section.getAttribute("data-down")),
        section.hasAttribute("data-siblings"),
        window.StrataExport.data.cap
      );
      if (!hood) { canvas.hidden = true; return; }
      capNote(section, hood);
      draw(canvas, list, hood);
      return;
    }
    fetch(canvas.getAttribute("data-src"), { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then(function (data) { draw(canvas, list, data); })
      .catch(function () { canvas.hidden = true; }); // the server-rendered list stays
  }
  init();
  doc.addEventListener("strata:page", init);

  // Esc goes back (the keyboard map's "Esc back"), unless a dialog or a field has it.
  doc.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || e.defaultPrevented) return;
    if (doc.querySelector("dialog[open]")) return;
    if (e.target.closest && e.target.closest("input, textarea, select")) return;
    history.back();
  });
})();

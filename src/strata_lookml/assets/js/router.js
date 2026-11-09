// Strata workbench static export: a hash router over the pages the server rendered.
//
// Only in the export (workbench/export.py inlines it before the other scripts). Each page is an
// inert <template data-route="/findings?status=new"> holding exactly what the live server
// returns inside <main> for that route; this file puts the one `#<route>` names into <main>.
// Templates keep the server's `/...` links; once a page is in <main> they become `#/...`, so a
// click, a middle-click and a copied link all stay inside the file. What the live pages fetch
// is in #strata-export-data: the ⌘K index, the graph and each finding's PR-comment lines.
//
// The file holds one focused graph page: any other focus or hop state is that page re-pointed
// (focus name, links) with graph.js drawing the neighbourhood from the embedded graph. A hash
// that is not a route is a link to the old single-page dashboard (`#<id>`): decoded first and
// raw second (its openHashTarget rules), then matched to a finding or object id, a `roadmap:`
// anchor or a section name.
//
// Safety: no HTML string is ever parsed. Templates are cloned; every text is textContent.
(function () {
  "use strict";

  // <routes> Pure: which template a route shows (tests run this under node over an export).
  function own(map, key) { return Object.prototype.hasOwnProperty.call(map, key); }

  function splitRoute(route) {
    var q = route.indexOf("?");
    return {
      path: q < 0 ? route : route.slice(0, q),
      params: new URLSearchParams(q < 0 ? "" : route.slice(q + 1)),
    };
  }

  // The graph route for a focus at a hop state, as links.graph_path writes it: `base` is the
  // focus's default route from Python, so its quoting is never repeated here.
  function graphHref(base, up, down, siblings) {
    var prefix = base.slice(0, base.indexOf("&"));
    var hops = up === down ? "&hops=" + up : "&up=" + up + "&down=" + down;
    return prefix + hops + (siblings ? "&siblings=1" : "");
  }

  // The text pr_text.pr_comment gives for these ids' records.
  function prComment(comments, ids) {
    var seen = Object.create(null), n = 0, blocks = [];
    ids.forEach(function (id) {
      if (seen[id] || !own(comments, id)) return;
      seen[id] = true;
      n += comments[id].n;
      blocks.push(comments[id].text);
    });
    if (!n) return null;
    var header = "**Strata** found " + n + " LookML " + (n === 1 ? "finding" : "findings") + ":";
    return [header, ""].concat(blocks).join("\n");
  }

  function makeRoutes(data, routes) {
    var pages = Object.create(null), nodes = Object.create(null), frame = null;
    routes.forEach(function (route) {
      pages[route] = true;
      var split = splitRoute(route);
      if (split.path === "/graph" && split.params.has("focus")) frame = route;
    });
    data.graph.nodes.forEach(function (n) { nodes[n.id] = n; });
    var home = data.aliases["/"][0];
    var byId = null;

    // An old fragment's id: a finding or object id. A PDT finding's id is also its node id
    // (`pdt:<view>`); the index lists findings last, so it opens the finding, which is what the
    // old page anchored (the ledger row).
    function idTarget(id) {
      if (!byId) {
        byId = Object.create(null);
        data.index.items.forEach(function (item) { byId[item.id] = item.path; });
      }
      return id in byId ? byId[id] : null;
    }

    function hops(value) { return value === "1" || value === "2" ? Number(value) : null; }

    // {route, field?, graph?, query?} for a route, or null when the export cannot show it.
    function resolve(route) {
      if (route in pages) return { route: route };
      if (own(data.aliases, route)) return { route: data.aliases[route][0], field: data.aliases[route][1] };
      var split = splitRoute(route), params = split.params;
      if (split.path === "/graph" && params.has("focus")) {
        var node = nodes[params.get("focus")];
        var both = params.has("hops") ? hops(params.get("hops")) : 1;
        var up = params.has("up") ? hops(params.get("up")) : both;
        var down = params.has("down") ? hops(params.get("down")) : both;
        var siblings = params.get("siblings") || "0";
        if (!node || !frame || !up || !down || (siblings !== "0" && siblings !== "1")) return null;
        return { route: frame, graph: { node: node, up: up, down: down, siblings: siblings === "1" } };
      }
      // Free text is not pre-rendered: the page without it, the text handed to ⌘K.
      if ((split.path === "/search" || split.path === "/findings") && params.has("q")) {
        var plain = "/search";
        if (split.path === "/findings") {
          plain = "/findings?status=" + (params.get("status") || "new");
          var category = params.get("category");
          if (category && category !== "all") plain += "&category=" + category;
          if (!(plain in pages)) plain = home;
        }
        return { route: plain, query: params.get("q").trim() };
      }
      return null;
    }

    function legacyTarget(id) {
      if (own(data.sections, id)) return data.sections[id];
      var target = idTarget(id);
      if (target) return target;
      if (id.indexOf("roadmap:") === 0) {
        var rest = id.slice("roadmap:".length);
        return idTarget(rest) || idTarget(rest.replace(/:\d+$/, "")) || "/overview";
      }
      return idTarget(id.replace(/:\d+$/, "")); // a suffixed duplicate anchor (`<id>:2`)
    }

    // The route an old dashboard fragment meant, or null.
    function legacy(raw) {
      var id = raw;
      try { id = decodeURIComponent(raw); } catch (_) { id = raw; }
      return legacyTarget(id) || (id !== raw ? legacyTarget(raw) : null);
    }

    return { home: home, resolve: resolve, legacy: legacy };
  }
  // </routes>

  var doc = document;
  var main = doc.querySelector("main");
  var dataEl = doc.getElementById("strata-export-data");
  if (!main || !dataEl) return;
  var data = JSON.parse(dataEl.textContent);
  var NAV = ["findings", "overview", "graph", "search"];

  var templates = Object.create(null);
  Array.prototype.forEach.call(doc.querySelectorAll("template[data-route]"), function (t) {
    templates[t.getAttribute("data-route")] = t;
  });
  var routes = makeRoutes(data, Object.keys(templates));

  function each(scope, selector, fn) { Array.prototype.forEach.call(scope.querySelectorAll(selector), fn); }

  function linkHashes(scope) {
    each(scope, "a[href]", function (a) {
      var href = a.getAttribute("href");
      if (href.charAt(0) === "/" && href.charAt(1) !== "/") a.setAttribute("href", "#" + href);
    });
  }

  function markNav(route) {
    var key = route.split(/[/?]/)[1];
    each(doc, "nav .navlink", function (a) {
      if (NAV.indexOf(key) >= 0 && a.getAttribute("href") === "#/" + key) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  }

  // Point the one focused graph page at another focus or hop state. graph.js draws it from the
  // embedded graph; the server's ring list and cap note describe the page's own focus, so go.
  function graphState(state) {
    var section = main.querySelector("[data-graph][data-focus]");
    if (!section) return;
    var node = state.node;
    var kind = own(data.graph_kinds, node.kind) ? data.graph_kinds[node.kind] : node.kind;
    section.setAttribute("data-focus", node.id);
    section.setAttribute("data-up", String(state.up));
    section.setAttribute("data-down", String(state.down));
    if (state.siblings) section.setAttribute("data-siblings", "");
    else section.removeAttribute("data-siblings");
    section.setAttribute("data-variant", "");
    var label = section.querySelector("[data-graph-focus]");
    if (label) {
      label.textContent = node.display_label;
      label.setAttribute("title", kind + " " + node.display_label);
    }
    var controls = {
      one: [1, 1, state.siblings, state.up === 1 && state.down === 1],
      two: [2, 2, state.siblings, state.up === 2 && state.down === 2],
      up: [state.up === 2 ? 1 : 2, state.down, state.siblings, state.up === 2],
      down: [state.up, state.down === 2 ? 1 : 2, state.siblings, state.down === 2],
      siblings: [state.up, state.down, !state.siblings, state.siblings],
    };
    each(section, "[data-control]", function (a) {
      var name = a.getAttribute("data-control");
      if (name === "page") {
        if (node.path) a.setAttribute("href", "#" + node.path);
        a.hidden = !node.path;
        return;
      }
      var c = controls[name];
      a.setAttribute("href", "#" + graphHref(node.graph, c[0], c[1], c[2]));
      if (c[3]) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
    each(section, "[data-graph-list], .gnote", function (el) { el.remove(); });
    doc.title = "Graph " + node.display_label + " · Strata workbench";
  }

  function notice(text) {
    var p = doc.createElement("p");
    p.className = "stale";
    p.setAttribute("role", "status");
    p.textContent = text;
    main.insertBefore(p, main.firstChild);
  }

  function show(found, message) {
    var template = templates[found.route];
    main.replaceChildren(template.content.cloneNode(true));
    doc.title = template.getAttribute("data-title") + " · Strata workbench";
    linkHashes(main);
    markNav(found.route);
    if (found.graph) graphState(found.graph);
    if (found.query) main.setAttribute("data-query", found.query);
    else main.removeAttribute("data-query");
    if (message) notice(message);
    window.scrollTo(0, 0);
    if (found.field) {
      var row = Array.prototype.find.call(main.querySelectorAll("[data-field]"), function (li) {
        return li.getAttribute("data-field") === found.field;
      });
      if (row) {
        row.classList.add("hit");
        row.scrollIntoView({ block: "center" });
      }
    }
    doc.dispatchEvent(new CustomEvent("strata:page"));
  }

  function route() {
    var hash = location.hash.slice(1);
    var target = hash;
    var message = null;
    if (!hash) {
      target = routes.home;
    } else if (hash.charAt(0) !== "/") {
      target = routes.legacy(hash);
      if (!target) {
        target = routes.home;
        message = "That link is not in this export; showing the findings.";
      }
    }
    if (target !== hash) history.replaceState(null, "", "#" + target);
    var found = routes.resolve(target);
    if (!found) {
      found = routes.resolve(routes.home);
      message = "That page is not in this export; showing the findings.";
    }
    show(found, message);
  }

  function go(href) {
    var hash = href.charAt(0) === "#" ? href : "#" + href;
    if (location.hash === hash) route();
    else location.hash = hash;
  }

  // The pages' GET forms (the Findings filter, Search): their query, routed like a link.
  doc.addEventListener("submit", function (e) {
    var action = e.target.getAttribute("action");
    if (!action || action.charAt(0) !== "/") return;
    e.preventDefault();
    go(action + "?" + new URLSearchParams(new FormData(e.target)).toString());
  });

  window.addEventListener("hashchange", route);
  window.StrataExport = {
    data: data,
    go: go,
    prComment: function (ids) { return prComment(data.comments, ids); },
  };
  linkHashes(doc.querySelector("nav") || doc);
  route();
})();

// Strata workbench: keyboard map and copy actions over server-rendered pages.
//
// Progressive enhancement only. Every page works without this file: tabs, category chips and
// pages are links, the filter is a GET form. Nothing here derives a status or filters rows;
// it reads what the server rendered (data-* attributes) and moves a cursor over it.
//
// Safety: DOM is built with createElement/textContent only. No HTML string is ever parsed
// (tests/test_workbench_findings.py bans the parsing sinks in this file).
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;
  var THEME_KEY = "strata-workbench-theme";
  var G_WINDOW_MS = 900;

  function $(selector, scope) { return (scope || doc).querySelector(selector); }
  function $all(selector, scope) { return Array.prototype.slice.call((scope || doc).querySelectorAll(selector)); }

  // --- toast and clipboard -------------------------------------------------------------

  var toastTimer = 0;
  function toast(message) {
    $all(".toast").forEach(function (t) { t.remove(); });
    var t = doc.createElement("div");
    t.className = "toast";
    t.setAttribute("role", "status");
    t.textContent = message;
    doc.body.appendChild(t);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.remove(); }, 2600);
  }

  function copyText(text, message) {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      toast("Clipboard unavailable — select the text and copy it");
      return;
    }
    navigator.clipboard.writeText(text).then(
      function () { toast(message); },
      function () { toast("Clipboard blocked — select the text and copy it"); }
    );
  }

  // --- theme ---------------------------------------------------------------------------

  var themeButton = $('[data-action="theme"]');
  function storedTheme() {
    try { return localStorage.getItem(THEME_KEY); } catch (_) { return null; }
  }
  function applyTheme(theme) {
    if (theme === "light") root.setAttribute("data-theme", "light");
    else root.removeAttribute("data-theme");
    if (themeButton) themeButton.textContent = theme === "light" ? "Dark" : "Light";
  }
  function toggleTheme() {
    var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
    applyTheme(next);
    try { localStorage.setItem(THEME_KEY, next); } catch (_) { /* per-viewer convenience only */ }
  }
  applyTheme(storedTheme());
  if (themeButton) {
    themeButton.hidden = false;
    themeButton.addEventListener("click", toggleTheme);
  }

  // --- help ----------------------------------------------------------------------------

  var help = $("#help");
  var helpButton = $('[data-action="help"]');
  function openHelp() {
    if (help && !help.open && typeof help.showModal === "function") help.showModal();
  }
  if (helpButton && help) {
    helpButton.hidden = false;
    helpButton.addEventListener("click", openHelp);
  }

  // --- findings list -------------------------------------------------------------------

  var list = findingsList($("[data-findings]"));

  function findingsList(section) {
    if (!section) return null;
    var rows = $all("[data-row]", section);
    var tabs = $all(".tabs .tab", section);
    var chips = $all("[data-chip]", section);
    var filter = $("[data-filter]", section);
    var count = $("[data-count]", section);
    var selectAll = $("[data-select-all]", section);
    var actionbar = $("[data-actionbar]", section);
    var cursor = 0;

    function checkbox(row) { return $("[data-select]", row); }
    function selected() { return rows.filter(function (r) { return r.classList.contains("sel"); }); }
    function ids(rs) {
      return rs.reduce(function (all, r) { return all.concat(r.getAttribute("data-ids").split(" ")); }, []);
    }

    function paint() {
      rows.forEach(function (r, i) {
        r.classList.toggle("cur", i === cursor);
        r.setAttribute("aria-current", i === cursor ? "true" : "false");
      });
      var n = ids(selected()).length;
      if (count) {
        count.textContent = n ? n + " selected" : "Cursor row";
        count.className = n ? "count" : "count zero";
      }
      if (selectAll) selectAll.checked = rows.length > 0 && selected().length === rows.length;
    }

    function move(delta) {
      if (!rows.length) return;
      cursor = Math.max(0, Math.min(rows.length - 1, cursor + delta));
      paint();
      rows[cursor].scrollIntoView({ block: "nearest" });
    }

    function setSelected(row, on) {
      row.classList.toggle("sel", on);
      var box = checkbox(row);
      if (box) box.checked = on;
    }

    function targets() {
      var picked = selected();
      if (picked.length) return picked;
      return rows.length ? [rows[cursor]] : [];
    }

    function copyComment() {
      var rs = targets();
      if (!rs.length) { toast("Nothing to copy"); return; }
      var blocks = rs.map(function (r) { return r.getAttribute("data-comment"); });
      var text = [section.getAttribute("data-comment-head"), ""].concat(blocks).join("\n");
      var n = ids(rs).length;
      copyText(text, "Copied PR comment for " + n + " finding" + (n === 1 ? "" : "s"));
    }

    function copyPaths() {
      var seen = [];
      targets().forEach(function (r) {
        (r.getAttribute("data-locations") || "").split("\n").forEach(function (p) {
          if (p && seen.indexOf(p) < 0) seen.push(p);
        });
      });
      if (!seen.length) { toast("No file:line on this finding"); return; }
      copyText(seen.join("\n"), "Copied " + (seen.length === 1 ? seen[0] : seen.length + " paths"));
    }

    function triageHint(verb) {
      toast(verb + " from the web arrives with S9; use `strata " + (verb === "Acknowledging" ? "ack" : "unack") + "`");
    }

    function cycleCategory() {
      var usable = chips.filter(function (c) {
        return !c.hasAttribute("data-empty") || c.getAttribute("aria-current") === "page";
      });
      var at = usable.findIndex(function (c) { return c.getAttribute("aria-current") === "page"; });
      var next = usable[(at + 1) % usable.length];
      if (next) location.href = next.href;
    }

    rows.forEach(function (row, i) {
      var box = checkbox(row);
      if (box) {
        box.disabled = false;
        box.addEventListener("change", function () { setSelected(row, box.checked); cursor = i; paint(); });
      }
      row.addEventListener("click", function (e) {
        if (e.target.closest("a, input, button")) return;
        cursor = i;
        paint();
      });
    });
    if (selectAll) {
      selectAll.disabled = rows.length === 0;
      selectAll.addEventListener("change", function () {
        rows.forEach(function (r) { setSelected(r, selectAll.checked); });
        paint();
      });
    }
    if (actionbar) {
      actionbar.hidden = false;
      actionbar.addEventListener("click", function (e) {
        var button = e.target.closest("[data-action]");
        if (!button) return;
        var action = button.getAttribute("data-action");
        if (action === "ack") triageHint("Acknowledging");
        else if (action === "unack") triageHint("Unacknowledging");
        else if (action === "comment") copyComment();
        else if (action === "path") copyPaths();
      });
    }
    paint();

    return {
      filter: filter,
      key: function (e) {
        var k = e.key;
        if (k === "j" || k === "ArrowDown") { move(1); return true; }
        if (k === "k" || k === "ArrowUp") { move(-1); return true; }
        if (k === "Enter" || k === "o") {
          var href = rows.length && rows[cursor].getAttribute("data-href");
          if (href) location.href = href;
          return true;
        }
        if (k === "x") {
          if (rows.length) { setSelected(rows[cursor], !rows[cursor].classList.contains("sel")); paint(); }
          return true;
        }
        if (k === "/") { if (filter) { filter.focus(); filter.select(); } return true; }
        if (k === "f") { cycleCategory(); return true; }
        if (/^[1-6]$/.test(k)) {
          var tab = tabs[Number(k) - 1];
          if (tab) location.href = tab.href;
          return true;
        }
        if (k === "a") { triageHint("Acknowledging"); return true; }
        if (k === "u") { triageHint("Unacknowledging"); return true; }
        if (k === "c") { copyComment(); return true; }
        if (k === "y") { copyPaths(); return true; }
        if (k === "Escape" && selected().length) {
          selected().forEach(function (r) { setSelected(r, false); });
          paint();
          return true;
        }
        return false;
      },
    };
  }

  // --- global keyboard -----------------------------------------------------------------

  var gPressedAt = 0;
  doc.addEventListener("keydown", function (e) {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
    if (help && help.open) return; // the dialog closes itself on Esc
    var typing = e.target.closest && e.target.closest("input:not([type=checkbox]), textarea, select");
    if (typing) {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    var k = e.key;
    if (gPressedAt && Date.now() - gPressedAt < G_WINDOW_MS) {
      gPressedAt = 0;
      var go = { f: "/findings", o: "/overview", g: "/graph" }[k];
      if (go) { e.preventDefault(); location.href = go; }
      return;
    }
    if (k === "g") { gPressedAt = Date.now(); return; }
    if (k === "?") { e.preventDefault(); openHelp(); return; }
    // Enter on a focused link or button keeps its native meaning.
    if (k === "Enter" && e.target.closest && e.target.closest("a, button")) return;
    if (list && list.key(e)) e.preventDefault();
  });
})();

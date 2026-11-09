// Detail pages: copy buttons. textContent only; no markup is ever built from page data.
(function () {
  "use strict";
  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return fallbackCopy(text); });
    }
    return Promise.resolve(fallbackCopy(text));
  }
  document.addEventListener("click", function (event) {
    var button = event.target.closest ? event.target.closest("[data-copy], [data-copy-from]") : null;
    if (!button || button.disabled) return;
    var text = button.getAttribute("data-copy");
    if (text === null) {
      var source = document.getElementById(button.getAttribute("data-copy-from"));
      text = source ? source.value : "";
    }
    var label = button.getAttribute("data-label") || button.textContent;
    button.setAttribute("data-label", label);
    copy(text).then(function (ok) {
      button.textContent = ok ? "Copied" : "Copy failed";
      setTimeout(function () { button.textContent = label; }, 1500);
    });
  });
})();

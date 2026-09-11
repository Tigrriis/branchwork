// Branchwork page script: tile clicks post points, the server sends back the
// re-rendered tree, and the page swaps it in. Also: confirm dialogs on
// destructive forms and auto-dismissing flashes.
(function () {
  "use strict";

  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  // ── Points ────────────────────────────────────────────────────────────
  var tree = document.getElementById("tree");
  if (tree) {
    var busy = false;

    function postPoints(tile, delta) {
      if (busy) return;
      var id = tile.dataset.task;
      busy = true;
      tile.classList.add("is-busy");
      fetch("/tasks/" + id + "/points", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ delta: delta }),
        credentials: "same-origin"
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
        .then(function (res) {
          if (!res.ok) { flash(res.body.message || "Could not update that task.", "error"); return; }
          tree.innerHTML = res.body.html;
          updateStats(res.body);
          var again = tree.querySelector('[data-task="' + id + '"]');
          if (again) again.classList.add("is-flash");
        })
        .catch(function () { flash("Network error. Try again.", "error"); })
        .finally(function () { busy = false; tile.classList.remove("is-busy"); });
    }

    tree.addEventListener("click", function (e) {
      var box = e.target.closest(".tile__box");
      if (!box || box.disabled || box.classList.contains("tile__box--add")) return;
      var tile = box.closest(".tile");
      if (!tile || !tile.dataset.task) return;
      e.preventDefault();
      postPoints(tile, e.shiftKey ? -1 : 1);
    });

    tree.addEventListener("contextmenu", function (e) {
      var box = e.target.closest(".tile__box");
      if (!box || box.disabled) return;
      var tile = box.closest(".tile");
      if (!tile || !tile.dataset.task) return;
      e.preventDefault();
      postPoints(tile, -1);
    });

    function updateStats(body) {
      var stats = document.getElementById("tree-stats");
      if (!stats) return;
      var done = stats.querySelector("[data-points-done]");
      var max = stats.querySelector("[data-points-max]");
      var bar = stats.querySelector("[data-points-bar]");
      if (done) done.textContent = body.points_done;
      if (max) max.textContent = body.points_max;
      if (bar) bar.style.width = body.percent + "%";
      Object.keys(body.counts || {}).forEach(function (k) {
        var el = stats.querySelector('[data-count="' + k + '"]');
        if (el) el.textContent = body.counts[k];
      });
    }
  }

  // ── Confirm before destructive forms ──────────────────────────────────
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.dataset && form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      e.preventDefault();
    }
  });

  // ── Flashes ───────────────────────────────────────────────────────────
  function flash(message, category) {
    var host = document.getElementById("flashes");
    if (!host) return;
    var el = document.createElement("div");
    el.className = "flash flash--" + (category || "info");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () { el.remove(); }, 4000);
  }
  Array.prototype.forEach.call(document.querySelectorAll(".flash"), function (el) {
    setTimeout(function () { el.remove(); }, 4500);
  });
})();

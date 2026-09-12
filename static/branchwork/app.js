// Branchwork page script.
//
// Everything that talks to the server sends JSON and swaps a server-rendered
// fragment back in, so the gate, lock and focus rules live in exactly one
// place and are never reimplemented here.
(function () {
  "use strict";

  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var tree = document.getElementById("tree");

  // ── Shared ────────────────────────────────────────────────────────────
  function flash(message, category) {
    var host = document.getElementById("flashes");
    if (!host) return;
    var el = document.createElement("div");
    el.className = "flash flash--" + (category || "info");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () { el.remove(); }, 4000);
  }

  function updateStats(body) {
    var stats = document.getElementById("tree-stats");
    if (!stats || body.points_max === undefined) return;
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

  function post(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(payload),
      credentials: "same-origin"
    }).then(function (r) {
      return r.json().then(function (j) { return { ok: r.ok, body: j }; });
    });
  }

  // ── Points ────────────────────────────────────────────────────────────
  if (tree) {
    var busy = false;

    tree.addEventListener("click", function (e) {
      var box = e.target.closest(".tile__box");
      if (!box || box.disabled || box.classList.contains("tile__box--add")) return;
      var tile = box.closest(".tile");
      if (!tile || !tile.dataset.task) return;
      e.preventDefault();
      movePoints(tile, e.shiftKey ? -1 : 1);
    });

    tree.addEventListener("contextmenu", function (e) {
      var box = e.target.closest(".tile__box");
      if (!box || box.disabled) return;
      var tile = box.closest(".tile");
      if (!tile || !tile.dataset.task) return;
      e.preventDefault();
      movePoints(tile, -1);
    });

    function movePoints(tile, delta) {
      if (busy) return;
      var id = tile.dataset.task;
      busy = true;
      tile.classList.add("is-busy");
      post("/tasks/" + id + "/points", { delta: delta })
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
  }

  // ── Dragging ──────────────────────────────────────────────────────────
  // Two kinds, one set of listeners: an idea onto a tier of the tree, and a
  // project between the focus and backburner lanes.
  var drag = null;   // {kind, id, from}

  var KINDS = {
    idea: { handle: ".idea", zone: ".tier__row, .tier-add" },
    project: { handle: ".prow", zone: "[data-focus-zone]" }
  };

  function zoneFor(node) {
    if (!drag || !node || !node.closest) return null;
    return node.closest(KINDS[drag.kind].zone);
  }

  function clearZones() {
    Array.prototype.forEach.call(document.querySelectorAll(".is-drop"),
      function (el) { el.classList.remove("is-drop"); });
  }

  function promoteIdea(ideaId, branchId, tier) {
    if (!ideaId || !branchId) return;
    post("/ideas/" + ideaId + "/promote", { branch_id: Number(branchId), tier: Number(tier) })
      .then(function (res) {
        if (!res.ok) { flash(res.body.message || "Could not add that idea.", "error"); return; }
        var list = document.getElementById("ideas-list");
        if (tree) tree.innerHTML = res.body.tree;
        if (list) list.innerHTML = res.body.ideas;
        updateStats(res.body);
        flash("“" + res.body.title + "” added to " + res.body.branch +
              ", tier " + res.body.tier + ".", "success");
      })
      .catch(function () { flash("Network error. Try again.", "error"); });
  }

  // The page header is outside #lanes, so the drop has to move it by hand.
  function updateFocusCounts(counts) {
    if (!counts) return;
    var map = { focus: "focus", backburner: "back", due: "due", no_action: "noaction" };
    Object.keys(map).forEach(function (key) {
      var el = document.querySelector("[data-count-" + map[key] + "]");
      if (el) el.textContent = counts[key];
    });
    [["due", "[data-chip-due]"], ["no_action", "[data-chip-noaction]"]].forEach(function (pair) {
      var chip = document.querySelector(pair[1]);
      if (chip) chip.classList.toggle("chip--warn", counts[pair[0]] > 0);
    });
  }

  function setFocus(projectId, focused) {
    post("/projects/" + projectId + "/focus", { focused: focused ? "1" : "0" })
      .then(function (res) {
        if (!res.ok) { flash(res.body.message || "Could not move that project.", "error"); return; }
        var lanes = document.getElementById("lanes");
        if (lanes) lanes.innerHTML = res.body.lists;
        updateFocusCounts(res.body.counts);
        flash(res.body.name + (res.body.focused ? " is in focus." : " is on the backburner."),
              "success");
      })
      .catch(function () { flash("Network error. Try again.", "error"); });
  }

  document.addEventListener("dragstart", function (e) {
    if (!e.target.closest) return;
    var kind = Object.keys(KINDS).filter(function (k) {
      return e.target.closest(KINDS[k].handle);
    })[0];
    if (!kind) return;
    var handle = e.target.closest(KINDS[kind].handle);
    drag = {
      kind: kind,
      id: handle.dataset.idea || handle.dataset.project,
      from: handle.closest("[data-focus-zone]")
    };
    e.dataTransfer.effectAllowed = "move";
    // Firefox refuses to start a drag with nothing on the transfer.
    e.dataTransfer.setData("text/plain", drag.id);
    handle.classList.add("is-dragging");
    document.body.classList.add("is-dragging-" + kind);
  });

  document.addEventListener("dragend", function () {
    if (drag) document.body.classList.remove("is-dragging-" + drag.kind);
    drag = null;
    Array.prototype.forEach.call(document.querySelectorAll(".is-dragging"),
      function (el) { el.classList.remove("is-dragging"); });
    clearZones();
  });

  document.addEventListener("dragover", function (e) {
    var zone = zoneFor(e.target);
    if (!zone) return;
    e.preventDefault();                       // without this, drop never fires
    e.dataTransfer.dropEffect = "move";
    zone.classList.add("is-drop");
  });

  document.addEventListener("dragleave", function (e) {
    var zone = zoneFor(e.target);
    if (zone && !zone.contains(e.relatedTarget)) zone.classList.remove("is-drop");
  });

  document.addEventListener("drop", function (e) {
    var zone = zoneFor(e.target);
    if (!zone) return;
    e.preventDefault();                       // and stop .tier-add navigating
    var moving = drag;
    clearZones();
    if (moving.kind === "idea") {
      promoteIdea(moving.id, zone.dataset.branch, zone.dataset.tier);
    } else if (zone !== moving.from) {        // dropping back home is a no-op
      setFocus(moving.id, zone.dataset.focusZone === "1");
    }
  });

  // Same destinations without dragging, for touch and keyboard.
  document.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-idea-place]");
    if (opener) {
      var panel = opener.closest(".idea").querySelector(".idea__place");
      if (panel) {
        panel.hidden = !panel.hidden;
        if (!panel.hidden) panel.querySelector("select").focus();
      }
      return;
    }
    var confirmer = e.target.closest("[data-idea-confirm]");
    if (confirmer) {
      var idea = confirmer.closest(".idea");
      var target = idea.querySelector("[data-idea-target]");
      var parts = ((target && target.value) || "").split(":");
      promoteIdea(idea.dataset.idea, parts[0], parts[1]);
    }
  });

  // ── Confirm before destructive forms ──────────────────────────────────
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.dataset && form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      e.preventDefault();
    }
  });

  // ── Flashes ───────────────────────────────────────────────────────────
  Array.prototype.forEach.call(document.querySelectorAll(".flash"), function (el) {
    setTimeout(function () { el.remove(); }, 4500);
  });
})();

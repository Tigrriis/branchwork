// Branchwork page script.
//
// Everything that talks to the server sends JSON and swaps a server-rendered
// fragment back in, so the gate, lock and focus rules live in exactly one
// place and are never reimplemented here.
(function () {
  "use strict";

  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var tree = document.getElementById("tree");

  // Pop-up words come from the copy catalogue, handed over as window.COPY.
  function say(key, values) {
    var text = (window.COPY || {})[key] || key;
    return text.replace(/\{(\w+)\}/g, function (whole, name) {
      return values && Object.prototype.hasOwnProperty.call(values, name) ? values[name] : whole;
    });
  }

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

  // Swap the tree in, letting each tier's fill run from its old level to its
  // new one. The new markup arrives already at the final level, so wind each
  // changed tier back to where it was, commit that, then let it go.
  function swapTree(html) {
    if (!tree) return;
    var before = {};
    Array.prototype.forEach.call(tree.querySelectorAll("[data-tier-key]"), function (el) {
      before[el.dataset.tierKey] = el.style.getPropertyValue("--fill");
    });
    tree.innerHTML = html;
    var moved = [];
    Array.prototype.forEach.call(tree.querySelectorAll("[data-tier-key]"), function (el) {
      var old = before[el.dataset.tierKey];
      var target = el.style.getPropertyValue("--fill");
      if (old === undefined || old === target) return;
      el.style.setProperty("--fill", old);
      moved.push([el, target]);
    });
    if (!moved.length) return;
    void tree.offsetHeight;                   // lay out at the old levels first
    moved.forEach(function (pair) { pair[0].style.setProperty("--fill", pair[1]); });
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
          if (!res.ok) { flash(res.body.message || say("points_failed"), "error"); return; }
          swapTree(res.body.html);
          updateStats(res.body);
          var again = tree.querySelector('[data-task="' + id + '"]');
          if (again) again.classList.add("is-flash");
        })
        .catch(function () { flash(say("network"), "error"); })
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
        if (!res.ok) { flash(res.body.message || say("idea_failed"), "error"); return; }
        var list = document.getElementById("ideas-list");
        swapTree(res.body.tree);
        if (list) list.innerHTML = res.body.ideas;
        updateStats(res.body);
        flash(say("idea_added", { title: res.body.title, scheme: res.body.branch, tier: res.body.tier }),
              "success");
      })
      .catch(function () { flash(say("network"), "error"); });
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
        if (!res.ok) { flash(res.body.message || say("focus_failed"), "error"); return; }
        var lanes = document.getElementById("lanes");
        if (lanes) lanes.innerHTML = res.body.lists;
        updateFocusCounts(res.body.counts);
        flash(say(res.body.focused ? "focused" : "backburnered", { name: res.body.name }),
              "success");
      })
      .catch(function () { flash(say("network"), "error"); });
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

  // ── Routines ──────────────────────────────────────────────────────────
  // An ability is a plain form. Take over its submit, post JSON, and swap the
  // bar it sits in, so the cooldown restarts without a reload. Registered
  // after the confirm handler above, which cancels an early use it was
  // refused, so a cancelled one arrives here already prevented.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form.matches || !form.matches("form[data-routine]")) return;
    var bar = form.closest("[data-routines]");
    if (!bar) return;
    e.preventDefault();
    if (form.classList.contains("is-busy")) return;
    form.classList.add("is-busy");
    var id = form.dataset.routine;
    post(form.action, { where: bar.dataset.routines })
      .then(function (res) {
        if (!res.ok) { flash(res.body.message || say("routine_failed"), "error"); return; }
        bar.innerHTML = res.body.html;
        bar.hidden = !bar.innerHTML.trim();
        if (bar.dataset.routines === "today") {
          bar.classList.toggle("abilities--quiet", !bar.querySelector("form[data-routine]"));
        }
        var again = bar.querySelector('[data-routine="' + id + '"]');
        if (again) again.classList.add("is-used");
        flash(say("routine_done", { title: res.body.title, n: res.body.every_days }), "success");
      })
      .catch(function () { flash(say("routine_failed"), "error"); })
      .finally(function () { form.classList.remove("is-busy"); });
  });

  // ── Plot switcher ─────────────────────────────────────────────────────
  // The sidebar opens itself on hover and focus through CSS. The script adds
  // the pin, the filter, Ctrl K, and the drawer on narrow screens.
  var rail = document.getElementById("rail");
  if (rail) {
    var root = document.documentElement;
    var railFilter = rail.querySelector("[data-rail-filter]");
    var railPin = rail.querySelector("[data-rail-pin]");

    var remember = function (pinned) {
      try {
        if (pinned) localStorage.setItem("rail", "pinned");
        else localStorage.removeItem("rail");
      } catch (e) { /* private window: the pin just lasts this page */ }
    };
    var showPin = function () {
      railPin.setAttribute("aria-pressed", root.dataset.rail === "pinned" ? "true" : "false");
    };
    showPin();
    railPin.addEventListener("click", function () {
      var pinned = root.dataset.rail !== "pinned";
      if (pinned) root.dataset.rail = "pinned";
      else delete root.dataset.rail;
      remember(pinned);
      showPin();
    });

    var openRail = function () {
      rail.classList.add("is-open");
      document.body.classList.add("rail-open");
    };
    var closeRail = function () {
      rail.classList.remove("is-open");
      document.body.classList.remove("rail-open");
    };
    var findPlot = function () {
      openRail();
      railFilter.focus();
      railFilter.select();
    };

    var applyRailFilter = function () {
      var q = railFilter.value.trim().toLowerCase();
      var shown = 0;
      Array.prototype.forEach.call(rail.querySelectorAll("[data-rail-group]"), function (group) {
        var any = false;
        Array.prototype.forEach.call(group.querySelectorAll("[data-rail-item]"), function (item) {
          var hit = !q || item.dataset.name.indexOf(q) !== -1;
          item.hidden = !hit;
          if (hit) { any = true; shown += 1; }
        });
        group.hidden = !any;
      });
      rail.querySelector("[data-rail-none]").hidden = !q || shown > 0;
    };
    railFilter.addEventListener("input", applyRailFilter);
    railFilter.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        var first = rail.querySelector("[data-rail-item]:not([hidden])");
        if (first) { e.preventDefault(); window.location.href = first.href; }
      } else if (e.key === "Escape") {
        railFilter.value = "";
        applyRailFilter();
        closeRail();
        railFilter.blur();
      }
    });

    rail.querySelector("[data-rail-search]").addEventListener("click", findPlot);
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        findPlot();
      }
    });
    document.addEventListener("click", function (e) {
      if (e.target.closest("[data-rail-open]")) {
        // Opened, not focused: on a phone, focusing the filter throws up the keyboard.
        if (rail.classList.contains("is-open")) closeRail();
        else openRail();
      } else if (rail.classList.contains("is-open") && !rail.contains(e.target)) {
        closeRail();
      }
    });
    rail.addEventListener("focusout", function (e) {
      if (!rail.contains(e.relatedTarget)) closeRail();
    });
  }

  // ── Flashes ───────────────────────────────────────────────────────────
  Array.prototype.forEach.call(document.querySelectorAll(".flash"), function (el) {
    setTimeout(function () { el.remove(); }, 4500);
  });
})();

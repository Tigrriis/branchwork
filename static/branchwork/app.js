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

  // Times the server writes in UTC (<time data-local-time>), shown in the
  // viewer's own time zone. The UTC text stays on hover.
  (function () {
    var times = document.querySelectorAll("time[data-local-time]");
    if (!times.length) return;
    var stamp = window.Intl && Intl.DateTimeFormat
      ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }) : null;
    Array.prototype.forEach.call(times, function (el) {
      var d = new Date(el.getAttribute("datetime"));
      if (isNaN(d)) return;
      el.title = el.textContent;
      el.textContent = stamp ? stamp.format(d) : d.toLocaleString();
    });
  })();

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
    drawThreads();
    tree.dispatchEvent(new CustomEvent("tree-swapped"));
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

  // The notes page has a script of its own; these are what it borrows.
  window.BRANCHWORK = { post: post, say: say, flash: flash };

  // Signed out, an unlocked notes key has no business staying in the
  // browser (vault.js keeps it in IndexedDB between pages).
  if (!document.body.classList.contains("has-rail") && window.indexedDB) {
    try { indexedDB.deleteDatabase("villainy-vault"); } catch (e) { /* nothing kept */ }
  }

  // ── Points ────────────────────────────────────────────────────────────
  if (tree) {
    var busy = false;

    // Touch has no shift-click, and iOS no right-click, so pressing and
    // holding takes a point away (or a claim back). Android raises its own
    // contextmenu for the same hold; whichever comes first does it, and the
    // click that ends the hold adds nothing.
    var hold = null, held = 0;
    var holdTarget = function (e) {
      var target = e.target.closest(".tile__box, .ultimate__box");
      return target && !target.disabled && !target.classList.contains("tile__box--add") ? target : null;
    };
    var takeBack = function (target) {
      held = Date.now();
      if (target.classList.contains("ultimate__box")) {
        claimUltimate(target.closest(".ultimate"), false);
        return;
      }
      var tile = target.closest(".tile");
      if (tile && tile.dataset.task) movePoints(tile, -1);
    };
    var letGo = function () { clearTimeout(hold); hold = null; };
    tree.addEventListener("pointerdown", function (e) {
      if (e.pointerType !== "touch") return;
      var target = holdTarget(e);
      if (!target) return;
      letGo();
      hold = setTimeout(function () {
        hold = null;
        if (navigator.vibrate) navigator.vibrate(12);
        takeBack(target);
      }, 500);
    });
    // A scroll starting under the finger cancels the pointer, and the hold.
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (kind) {
      tree.addEventListener(kind, letGo);
    });

    tree.addEventListener("click", function (e) {
      if (Date.now() - held < 800) { e.preventDefault(); return; }
      var disc = e.target.closest(".ultimate__box");
      if (disc) {
        if (disc.disabled) return;
        e.preventDefault();
        claimUltimate(disc.closest(".ultimate"), !e.shiftKey);
        return;
      }
      var box = e.target.closest(".tile__box");
      if (!box || box.disabled || box.classList.contains("tile__box--add")) return;
      var tile = box.closest(".tile");
      if (!tile || !tile.dataset.task) return;
      e.preventDefault();
      movePoints(tile, e.shiftKey ? -1 : 1);
    });

    tree.addEventListener("contextmenu", function (e) {
      if (Date.now() - held < 800) { e.preventDefault(); return; }
      if (hold !== null) {
        var target = holdTarget(e);
        letGo();
        if (target) { e.preventDefault(); takeBack(target); return; }
      }
      var disc = e.target.closest(".ultimate__box");
      if (disc) {
        if (disc.disabled) return;
        e.preventDefault();
        claimUltimate(disc.closest(".ultimate"), false);
        return;
      }
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
      post("/machinations/" + id + "/points", { delta: delta })
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

    // An ultimate is claimed rather than pointed: one click lights it, and
    // shift-click or right-click takes it back. The tree comes back
    // re-rendered like it does for points; the burst is only for the
    // moment it first lights, so it is added here, not by the template.
    function claimUltimate(el, achieved) {
      if (busy || !el) return;
      var id = el.dataset.ultimate;
      var wasLit = el.classList.contains("ultimate--achieved");
      busy = true;
      el.classList.add("is-busy");
      post("/ultimates/" + id + "/achieve", { achieved: achieved })
        .then(function (res) {
          if (!res.ok) { flash(res.body.message || say("ultimate_failed"), "error"); return; }
          swapTree(res.body.html);
          var again = tree.querySelector('[data-ultimate="' + id + '"]');
          if (again && !wasLit && again.classList.contains("ultimate--achieved")) again.classList.add("is-lit");
        })
        .catch(function () { flash(say("network"), "error"); })
        .finally(function () { busy = false; el.classList.remove("is-busy"); });
    }
  }

  // ── Dragging ──────────────────────────────────────────────────────────
  // One set of listeners: an idea onto a tier of the tree, a project between
  // the focus and backburner lanes, a thread from tile to tile, the end of a
  // thread onto another tile, a tile to another tier or scheme, and a note
  // onto a folder of the notes explorer.
  var drag = null;   // {kind, id, from}

  // The first kind whose handle the drag starts in wins, so a tile's thread
  // handle, which sits inside the tile, still starts a thread.
  var KINDS = {
    idea: { handle: ".idea", zone: ".tier__row, .tier-add" },
    project: { handle: ".ptile, .btile", zone: "[data-focus-zone]" },
    thread: { handle: ".tile__thread", zone: ".tile[data-task], .ultimate[data-ultimate]" },
    end: { handle: ".thread-end", zone: ".tile[data-task], .ultimate[data-ultimate]" },
    task: { handle: ".tile[data-task]", zone: ".tier__row, .tier-add[data-branch]" },
    // A scheme also lands on another plot in the sidebar, which moves it there.
    scheme: { handle: ".col__foot", zone: ".col[data-branch], .col--add, .rail__item[data-project]" },
    note: { handle: ".nx-note", zone: "[data-drop-folder]" }
  };

  // On a touch screen pressing and holding a tile takes a point away, so a
  // tile is only dragged with a mouse or pen. The machination form moves it
  // there instead.
  var lastPointer = "mouse";
  document.addEventListener("pointerdown", function (e) { lastPointer = e.pointerType; }, true);

  function zoneFor(node) {
    if (!drag || !node || !node.closest) return null;
    var zone = node.closest(KINDS[drag.kind].zone);
    // Nothing leads on from an ultimate, so the near end of a thread cannot
    // land on one.
    if (zone && drag.kind === "end" && drag.end === "from" && zone.dataset.ultimate) return null;
    // A scheme dropped on the plot it is already in goes nowhere.
    if (zone && drag.kind === "scheme" && zone.dataset.project &&
        String(zone.dataset.project) === String(window.BRANCHWORK_PROJECT)) return null;
    return zone;
  }

  function clearZones() {
    Array.prototype.forEach.call(document.querySelectorAll(".is-drop, .is-insert-before, .is-insert-after"),
      function (el) { el.classList.remove("is-drop", "is-insert-before", "is-insert-after"); });
    var marker = document.querySelector(".col-marker");
    if (marker) marker.remove();
  }

  // Where a dragged scheme would land: before the column under the pointer
  // when it is over that column's left half, after it over the right half,
  // and last when over "Add a scheme". ``gap`` is the column whose left or
  // right gap the marker sits in.
  function columnSpot(zone, x) {
    if (zone.classList.contains("col--add")) return { before: null, gap: zone, side: "left" };
    var r = zone.getBoundingClientRect();
    if (x < r.left + r.width / 2) return { before: zone.dataset.branch, gap: zone, side: "left" };
    var next = zone.nextElementSibling;
    while (next && !next.matches(".col[data-branch], .col--add")) next = next.nextElementSibling;
    return { before: next && next.dataset.branch ? next.dataset.branch : null, gap: zone, side: "right" };
  }

  function markColumn(zone, x) {
    if (!tree) return;
    var spot = columnSpot(zone, x);
    var marker = tree.querySelector(".col-marker");
    if (!marker) {
      marker = document.createElement("div");
      marker.className = "col-marker";
      marker.setAttribute("aria-hidden", "true");
      tree.appendChild(marker);
    }
    var half = (parseFloat(getComputedStyle(tree).columnGap) || 24) / 2;
    var col = spot.gap;
    var left = spot.side === "left" ? col.offsetLeft - half : col.offsetLeft + col.offsetWidth + half;
    marker.style.left = Math.max(0, left - 1.5) + "px";
    marker.style.top = col.offsetTop + "px";
    marker.style.height = col.offsetHeight + "px";
  }

  // A scheme dropped on a plot in the sidebar moves there, machinations and
  // all. Links to the rest of this plot cannot follow it, so when there are
  // any the server says how many and the move is confirmed before it posts
  // again.
  function moveSchemeToPlot(branchId, projectId, confirmed) {
    if (!branchId || !projectId) return;
    post("/schemes/" + branchId + "/move-to", { project_id: Number(projectId), confirm: !!confirmed })
      .then(function (res) {
        if (res.body && res.body.needs_confirm) {
          if (window.confirm(res.body.message)) moveSchemeToPlot(branchId, projectId, true);
          return;
        }
        if (!res.ok) { flash(res.body.message || say("scheme_move_failed"), "error"); return; }
        swapTree(res.body.html);
        updateStats(res.body);
        flash(res.body.message, "success");
        if (res.body.cut_message) flash(res.body.cut_message, "info");
      })
      .catch(function () { flash(say("network"), "error"); });
  }

  function reorderScheme(branchId, beforeId) {
    if (!branchId || String(branchId) === String(beforeId)) return;
    post("/schemes/" + branchId + "/reorder", { before: beforeId ? Number(beforeId) : null })
      .then(function (res) {
        if (!res.ok) { flash(res.body.message || say("scheme_move_failed"), "error"); return; }
        if (res.body.moved) swapTree(res.body.html);
      })
      .catch(function () { flash(say("network"), "error"); });
  }

  // Where in a tier a dragged tile would land: before the first tile the
  // pointer is ahead of, reading the row left to right and line by line
  // (rows wrap), or after the last one. The tile being dragged is skipped,
  // so dropping it back on its own spot changes nothing.
  function insertSpot(zone, x, y) {
    if (!zone.classList.contains("tier__row")) return null;
    var tiles = Array.prototype.filter.call(zone.querySelectorAll(".tile[data-task]"),
      function (t) { return t.dataset.task !== String(drag.id); });
    for (var i = 0; i < tiles.length; i++) {
      var r = tiles[i].getBoundingClientRect();
      if (y < r.top || (y <= r.bottom && x < r.left + r.width / 2)) return { tile: tiles[i], after: false };
    }
    return tiles.length ? { tile: tiles[tiles.length - 1], after: true } : null;
  }

  function markInsert(zone, x, y) {
    Array.prototype.forEach.call(document.querySelectorAll(".is-insert-before, .is-insert-after"),
      function (el) { el.classList.remove("is-insert-before", "is-insert-after"); });
    var spot = insertSpot(zone, x, y);
    if (spot) spot.tile.classList.add(spot.after ? "is-insert-after" : "is-insert-before");
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

  // A tile dropped on a tier row lands where the marker showed, in its own
  // tier or another; on a scheme's "+ New tier", at the start of a new one.
  // The tree comes back re-rendered, as it does for points.
  function moveTask(taskId, branchId, tier, beforeId) {
    if (!taskId || !branchId || !tier) return;
    post("/machinations/" + taskId + "/move", {
      branch_id: Number(branchId), tier: Number(tier), before: beforeId ? Number(beforeId) : null
    })
      .then(function (res) {
        if (!res.ok) { flash(res.body.message || say("move_failed"), "error"); return; }
        if (!res.body.moved) return;
        swapTree(res.body.html);
        updateStats(res.body);
        var again = tree && tree.querySelector('[data-task="' + taskId + '"]');
        if (again) again.classList.add("is-flash");
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
      if (chip) chip.hidden = !(counts[pair[0]] > 0);
    });
  }

  function setFocus(projectId, focused) {
    post("/plots/" + projectId + "/focus", { focused: focused ? "1" : "0" })
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
    if (kind === "task" && lastPointer === "touch") { e.preventDefault(); return; }
    // A scheme is dragged by its name bar but moves as the whole column.
    var moving = kind === "scheme" ? handle.closest(".col") : handle;
    drag = {
      kind: kind,
      id: kind === "task" ? handle.dataset.task : kind === "scheme" ? moving.dataset.branch :
        handle.dataset.idea || handle.dataset.project || handle.dataset.threadFrom ||
        handle.dataset.threadEnd || handle.dataset.note,
      end: handle.dataset.end,
      from: handle.closest("[data-focus-zone], .tier__row")
    };
    e.dataTransfer.effectAllowed = "move";
    // Firefox refuses to start a drag with nothing on the transfer.
    e.dataTransfer.setData("text/plain", drag.id);
    if (kind === "scheme" && e.dataTransfer.setDragImage) {
      var box = moving.getBoundingClientRect();
      e.dataTransfer.setDragImage(moving, e.clientX - box.left, e.clientY - box.top);
    }
    moving.classList.add("is-dragging");
    document.body.classList.add("is-dragging-" + kind);
  });

  document.addEventListener("dragend", function () {
    if (drag) document.body.classList.remove("is-dragging-" + drag.kind);
    drag = null;
    Array.prototype.forEach.call(document.querySelectorAll(".is-dragging"),
      function (el) { el.classList.remove("is-dragging"); });
    clearZones();
  });

  // One zone lit at a time: whichever the pointer is over, and none over
  // anywhere a drop would do nothing. Leaving is judged here rather than on
  // dragleave, which also fires crossing the tiles inside a zone and, in
  // Chrome, without saying where the pointer went.
  document.addEventListener("dragover", function (e) {
    var zone = zoneFor(e.target);
    if (!zone) {
      if (drag) clearZones();
      // The end of a thread can be dropped anywhere: off the tree unthreads
      // it. Escape still cancels, since a cancelled drag never drops.
      if (drag && drag.kind === "end") { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }
      return;
    }
    e.preventDefault();                       // without this, drop never fires
    e.dataTransfer.dropEffect = "move";
    if (!zone.classList.contains("is-drop")) { clearZones(); zone.classList.add("is-drop"); }
    if (drag.kind === "task") markInsert(zone, e.clientX, e.clientY);
    if (drag.kind === "scheme" && !zone.dataset.project) markColumn(zone, e.clientX);
  });

  document.addEventListener("dragleave", function (e) {
    var zone = zoneFor(e.target);
    if (zone && e.relatedTarget && !zone.contains(e.relatedTarget)) zone.classList.remove("is-drop");
  });

  document.addEventListener("drop", function (e) {
    var zone = zoneFor(e.target);
    if (!zone && drag && drag.kind === "end") {
      e.preventDefault();
      // Over a column but not a tile is a miss, not a removal: only a drop
      // clear of every scheme unthreads.
      if (!(e.target.closest && e.target.closest(".col"))) unthread(drag.id);
      clearZones();
      return;
    }
    if (!zone) return;
    e.preventDefault();                       // and stop .tier-add navigating
    var moving = drag;
    clearZones();
    if (moving.kind === "idea") {
      promoteIdea(moving.id, zone.dataset.branch, zone.dataset.tier);
    } else if (moving.kind === "thread") {
      threadTasks(moving.id, zone.dataset.task, zone.dataset.ultimate);
    } else if (moving.kind === "end") {
      moveThreadEnd(moving.id, moving.end, zone.dataset.task, zone.dataset.ultimate);
    } else if (moving.kind === "task") {
      var spot = insertSpot(zone, e.clientX, e.clientY);
      var before = spot && !spot.after ? spot.tile.dataset.task : null;
      moveTask(moving.id, zone.dataset.branch, zone.dataset.tier, before);
    } else if (moving.kind === "scheme" && zone.dataset.project) {
      moveSchemeToPlot(moving.id, zone.dataset.project);
    } else if (moving.kind === "scheme") {
      reorderScheme(moving.id, columnSpot(zone, e.clientX).before);
    } else if (moving.kind === "note") {
      // The notes script owns the explorer, so it does the moving.
      document.dispatchEvent(new CustomEvent("note-drop",
        { detail: { id: moving.id, folder: zone.dataset.dropFolder } }));
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

  // ── Status menus ──────────────────────────────────────────────────────
  // A tile's status pill is a <details>, so it opens without the script. The
  // script only closes it again: on a click anywhere else, on Escape, and
  // when another one opens, so at most one menu hangs over the tiles.
  function closeStatusMenus(except) {
    Array.prototype.forEach.call(document.querySelectorAll("details.spick[open]"),
      function (el) { if (el !== except) el.open = false; });
  }
  document.addEventListener("click", function (e) {
    closeStatusMenus(e.target.closest && e.target.closest("details.spick"));
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeStatusMenus(null);
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

  // ── Threads ───────────────────────────────────────────────────────────
  // The server says which pairs are threaded; where the tiles actually sit is
  // only known here, so the shapes are measured from the laid-out tree.
  // Arrows are routed through the space that holds no tiles: the band above
  // or below a row of tiles, and the gutter between two schemes. The corners
  // are rounded off, so what reads on the page is a curve that goes around
  // the tiles rather than through them.
  function roundedPath(points, radius) {
    var pts = points.filter(function (p, i) {
      return i === 0 || Math.abs(p.x - points[i - 1].x) > 0.5 || Math.abs(p.y - points[i - 1].y) > 0.5;
    });
    if (pts.length < 2) return "";
    var d = "M" + pts[0].x + " " + pts[0].y;
    for (var i = 1; i < pts.length - 1; i++) {
      var prev = pts[i - 1], here = pts[i], next = pts[i + 1];
      var into = Math.sqrt(Math.pow(here.x - prev.x, 2) + Math.pow(here.y - prev.y, 2));
      var away = Math.sqrt(Math.pow(next.x - here.x, 2) + Math.pow(next.y - here.y, 2));
      var r = Math.min(radius, into / 2, away / 2);
      d += " L" + (here.x + (prev.x - here.x) * (r / into)) + " " + (here.y + (prev.y - here.y) * (r / into));
      d += " Q" + here.x + " " + here.y + " " +
           (here.x + (next.x - here.x) * (r / away)) + " " + (here.y + (next.y - here.y) * (r / away));
    }
    return d + " L" + pts[pts.length - 1].x + " " + pts[pts.length - 1].y;
  }

  function drawThreads() {
    if (!tree) return;
    var svg = tree.querySelector(".threads");
    if (!svg) return;
    // Measure the tree without the overlay. It sits inside the tree, so
    // sized from the tree's scroll size it would count itself, and could only
    // ever grow: once the columns got shorter, the tree kept a band of empty
    // height below them and a scrollbar of its own that swallowed the wheel.
    svg.setAttribute("width", 0);
    svg.setAttribute("height", 0);
    var width = tree.scrollWidth, height = tree.scrollHeight;
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    var frame = tree.getBoundingClientRect();

    // Measured in the tree's own content box, so the arrows stay with the
    // tiles when it is scrolled sideways.
    function boxOf(el) {
      if (!el) return null;
      var r = el.getBoundingClientRect();
      return {
        left: r.left - frame.left + tree.scrollLeft,
        right: r.right - frame.left + tree.scrollLeft,
        top: r.top - frame.top + tree.scrollTop,
        bottom: r.bottom - frame.top + tree.scrollTop,
        cx: r.left + r.width / 2 - frame.left + tree.scrollLeft,
        cy: r.top + r.height / 2 - frame.top + tree.scrollTop,
        h: r.height
      };
    }
    function tileOf(id) { return tree.querySelector('.tile[data-task="' + id + '"]'); }
    function discOf(id) { return tree.querySelector('.ultimate[data-ultimate="' + id + '"]'); }

    // The clear band on one side of a tile's row: half way to the next row,
    // or a little clear of the tiles when there is no next row.
    function laneNear(tile, down) {
      var col = tile.closest(".col");
      var rows = Array.prototype.slice.call(col.querySelectorAll(".tier__row"));
      var row = tile.closest(".tier__row");
      var here = boxOf(row);
      var beside = rows[rows.indexOf(row) + (down ? 1 : -1)];
      var edge = beside ? boxOf(beside) : null;
      if (down) return edge ? (here.bottom + edge.top) / 2 : here.bottom + 24;
      return edge ? (edge.bottom + here.top) / 2 : here.top - 16;
    }

    // Three passes: work out every route, then spread the ones that would
    // share a band or meet at the same point on a tile, then draw.
    var routes = [];
    var threadId = function (path) { return path.parentNode.dataset.thread; };
    var endNodes = function (id) {
      return tree.querySelectorAll('.thread-end[data-thread-end="' + id + '"]');
    };
    Array.prototype.forEach.call(svg.querySelectorAll(".thread__line"), function (path) {
      var arrow = path.parentNode.querySelector(".thread__arrow");
      // A thread ends at another tile or at a scheme's ultimate, which sits
      // alone under the tiers, so it is reached along its own centre line
      // rather than through a band between rows.
      var intoDisc = !!path.dataset.toUltimate;
      var fromTile = tileOf(path.dataset.from);
      var toTile = intoDisc ? discOf(path.dataset.toUltimate) : tileOf(path.dataset.to);
      if (!fromTile || !toTile) {
        path.removeAttribute("d");
        arrow.setAttribute("hidden", "hidden");
        Array.prototype.forEach.call(endNodes(threadId(path)), function (n) { n.hidden = true; });
        return;
      }
      arrow.removeAttribute("hidden");
      var a = boxOf(fromTile.querySelector(".tile__box"));
      var b = boxOf(toTile.querySelector(intoDisc ? ".ultimate__box" : ".tile__box"));
      var aRow = fromTile.closest(".tier__row"), bRow = intoDisc ? null : toTile.closest(".tier__row");
      var aCol = fromTile.closest(".col"), bCol = toTile.closest(".col");
      var toTheRight = b.cx >= a.cx;
      // Arrows leave and arrive at a tile's side: the plate and the label sit
      // under it, and running through those reads as a mistake.
      var edgeA = toTheRight ? a.right : a.left;
      var edgeB = toTheRight ? b.left : b.right;
      var outA = toTheRight ? 1 : -1;
      var sameRow = !intoDisc && (aRow === bRow || Math.abs(boxOf(aRow).top - boxOf(bRow).top) < 4);
      var route = {
        path: path, arrow: arrow, a: a, b: b,
        leaves: path.dataset.from + (toTheRight ? ":right" : ":left"),
        arrives: (intoDisc ? "u" + path.dataset.toUltimate : path.dataset.to) + (toTheRight ? ":left" : ":right")
      };

      if (sameRow && Math.abs(edgeB - edgeA) < 52) {
        // Neighbours in a row: straight across the gap between them.
        route.lane = null;
        route.build = function (nudge, from, to) {
          return [{ x: edgeA + outA * 2, y: a.cy + from }, { x: edgeB - outA * 3, y: b.cy + to }];
        };
        routes.push(route);
        return;
      }

      var laneA, laneB;
      if (sameRow) {
        laneA = laneB = laneNear(fromTile, true);
      } else if (intoDisc) {
        laneA = laneNear(fromTile, b.top > boxOf(aRow).top);
        laneB = b.cy;
      } else {
        var down = boxOf(bRow).top > boxOf(aRow).top;
        laneA = laneNear(fromTile, down);
        laneB = laneNear(toTile, !down);
      }
      // Down the gap beside the tile, not through its neighbour.
      var gapA = edgeA + outA * 8, gapB = edgeB - outA * 8;
      var cross = null;
      if (Math.abs(laneA - laneB) > 4) {
        // Crossing between two bands happens where there are no tiles: the
        // gutter beside the scheme being entered, or one scheme's own margin.
        if (aCol !== bCol) {
          var from = boxOf(aCol), to = boxOf(bCol);
          cross = to.left > from.right ? to.left - 12 : to.right + 12;
        } else {
          var col = boxOf(aCol);
          cross = (a.left - col.left) > (col.right - a.right) ? col.left + 14 : col.right - 14;
        }
      }
      route.lane = laneA;
      route.build = function (nudge, from, to) {
        var here = laneA + nudge, there = laneB + nudge;
        var points = [{ x: edgeA + outA * 2, y: a.cy + from }, { x: gapA, y: a.cy + from },
                      { x: gapA, y: here }];
        if (cross !== null) points.push({ x: cross, y: here }, { x: cross, y: there });
        points.push({ x: gapB, y: there }, { x: gapB, y: b.cy + to },
                    { x: edgeB - outA * 3, y: b.cy + to });
        return points;
      };
      routes.push(route);
    });

    var bands = {};
    routes.forEach(function (route) {
      if (route.lane === null) return;
      var key = Math.round(route.lane / 10);
      (bands[key] = bands[key] || []).push(route);
    });
    Object.keys(bands).forEach(function (key) {
      bands[key].forEach(function (route, i) {
        route.nudge = (i - (bands[key].length - 1) / 2) * 7;
      });
    });

    // A tile's own side: what leaves sits a little above the middle and what
    // arrives a little below, so the two never meet in one line.
    var ends = {};
    routes.forEach(function (route) {
      (ends[route.leaves] = ends[route.leaves] || []).push({ route: route, leaving: true });
      (ends[route.arrives] = ends[route.arrives] || []).push({ route: route, leaving: false });
    });
    Object.keys(ends).forEach(function (key) {
      [true, false].forEach(function (leaving) {
        var same = ends[key].filter(function (end) { return end.leaving === leaving; });
        same.forEach(function (end, i) {
          var box = leaving ? end.route.a : end.route.b;
          var room = Math.max(0, box.h / 2 - 12);
          var step = (i - (same.length - 1) / 2) * 8;
          var offset = (leaving ? -5 : 5) + step;
          offset = Math.max(-room, Math.min(room, offset));
          if (leaving) end.route.from = offset; else end.route.to = offset;
        });
      });
    });

    routes.forEach(function (route) {
      route.path.setAttribute("d",
        roundedPath(route.build(route.nudge || 0, route.from || 0, route.to || 0), 18));
      // Half way along, pointing the way the line is going at that moment.
      var length = route.path.getTotalLength();
      var middle = route.path.getPointAtLength(length / 2);
      var before = route.path.getPointAtLength(Math.max(0, length / 2 - 4));
      var after = route.path.getPointAtLength(Math.min(length, length / 2 + 4));
      var angle = Math.atan2(after.y - before.y, after.x - before.x) * 180 / Math.PI;
      route.arrow.setAttribute("transform",
        "translate(" + middle.x + " " + middle.y + ") rotate(" + angle + ")");
      // The nodes sit on the line's two ends, where it meets each tile.
      var ends = { from: route.path.getPointAtLength(0), to: route.path.getPointAtLength(length) };
      Array.prototype.forEach.call(endNodes(threadId(route.path)), function (node) {
        var at = ends[node.dataset.end];
        node.style.left = at.x + "px";
        node.style.top = at.y + "px";
        node.hidden = false;
      });
    });
  }

  // One end of a thread dropped on another tile, or on a scheme's ultimate
  // for the far end, moves that end. Back where it was is a no-op.
  function moveThreadEnd(threadId, end, toId, toUltimateId) {
    if (!threadId || (!toId && !toUltimateId)) return;
    var payload = toUltimateId ? { end: end, to_ultimate: Number(toUltimateId) } : { end: end, to: Number(toId) };
    post("/threads/" + threadId + "/move", payload)
      .then(function (res) {
        if (!res.ok) { flash(res.body.message || say("thread_failed"), "error"); return; }
        if (res.body.moved) swapTree(res.body.html);
      })
      .catch(function () { flash(say("network"), "error"); });
  }

  // An end dropped clear of the tree takes the thread with it.
  function unthread(threadId) {
    if (!threadId) return;
    post("/threads/" + threadId + "/delete", {})
      .then(function (res) {
        if (!res.ok) { flash(res.body.message || say("thread_failed"), "error"); return; }
        swapTree(res.body.html);
        flash(say("thread_removed"), "info");
      })
      .catch(function () { flash(say("network"), "error"); });
  }

  function threadTasks(fromId, toId, toUltimateId) {
    if (!fromId || (!toId && !toUltimateId) || String(fromId) === String(toId)) return;
    var payload = toUltimateId ? { to_ultimate: Number(toUltimateId) } : { to: Number(toId) };
    post("/machinations/" + fromId + "/threads", payload)
      .then(function (res) {
        if (!res.ok) { flash(res.body.message || say("thread_failed"), "error"); return; }
        swapTree(res.body.html);
      })
      .catch(function () { flash(say("network"), "error"); });
  }

  if (tree) {
    drawThreads();
    var redraw = null;
    var laterDraw = function () {
      if (redraw) cancelAnimationFrame(redraw);
      redraw = requestAnimationFrame(function () { redraw = null; drawThreads(); });
    };
    window.addEventListener("resize", laterDraw);
    if (window.ResizeObserver) new ResizeObserver(laterDraw).observe(tree);
  }

  // ── Panning ───────────────────────────────────────────────────────────
  // The tree scrolls sideways under a held mouse: press on any empty part of
  // the canvas (a column's ground, the gap between columns, the space around
  // a row of tiles) and drag. Anything that drags, clicks or types for
  // itself is left alone, and a pan does not start until the pointer has
  // moved a few pixels, so a plain click on the ground stays a click. Touch
  // screens scroll on their own.
  if (tree) {
    var pan = null, panned = false;
    var PAN_LEAVES = 'a, button, input, select, textarea, label, [draggable="true"], ' +
      '.tile, .col__foot, .thread-end, .tier-name, .quick-add, .ultimate__box, .idea';
    tree.addEventListener("pointerdown", function (e) {
      if (e.button !== 0 || e.pointerType === "touch" || !e.target.closest) return;
      if (e.target.closest(PAN_LEAVES)) return;
      pan = { id: e.pointerId, x: e.clientX, left: tree.scrollLeft, moved: false };
    });
    tree.addEventListener("pointermove", function (e) {
      if (!pan || e.pointerId !== pan.id) return;
      var dx = e.clientX - pan.x;
      if (!pan.moved) {
        if (Math.abs(dx) < 4) return;
        pan.moved = true;
        tree.classList.add("is-panning");
        try { tree.setPointerCapture(pan.id); } catch (err) { /* no capture, no matter */ }
        if (window.getSelection) window.getSelection().removeAllRanges();
      }
      tree.scrollLeft = pan.left - dx;
    });
    var endPan = function (e) {
      if (!pan || (e && e.pointerId !== undefined && e.pointerId !== pan.id)) return;
      if (pan.moved) {
        panned = true;
        tree.classList.remove("is-panning");
        try { tree.releasePointerCapture(pan.id); } catch (err) { /* already gone */ }
        setTimeout(function () { panned = false; }, 0);
      }
      pan = null;
    };
    tree.addEventListener("pointerup", endPan);
    tree.addEventListener("pointercancel", endPan);
    // The release at the end of a pan is not a click on whatever is under it.
    tree.addEventListener("click", function (e) {
      if (panned) { e.preventDefault(); e.stopPropagation(); }
    }, true);
  }

  // ── Tier names ────────────────────────────────────────────────────────
  // The field on the line above each tier. It is sized to its words, saves
  // on Enter or on leaving once the name has changed, and Escape puts the
  // old name back. The tree comes back re-rendered, as it does for points.
  if (tree) {
    var sizeTierName = function (input) {
      var mirror = document.getElementById("tier-name-mirror");
      if (!mirror) {
        mirror = document.createElement("span");
        mirror.id = "tier-name-mirror";
        mirror.className = "tier-name__mirror";
        mirror.setAttribute("aria-hidden", "true");
        document.body.appendChild(mirror);
      }
      mirror.textContent = input.value || input.placeholder;
      input.style.width = (mirror.offsetWidth + 22) + "px";
    };
    var sizeTierNames = function () {
      Array.prototype.forEach.call(tree.querySelectorAll(".tier-name__input"), sizeTierName);
    };
    sizeTierNames();
    tree.addEventListener("tree-swapped", sizeTierNames);

    var saveTierName = function (form) {
      var input = form.querySelector(".tier-name__input");
      var name = input.value.trim();
      if (name === (input.defaultValue || "").trim()) { input.value = input.defaultValue; sizeTierName(input); return; }
      input.disabled = true;
      post("/schemes/" + form.dataset.branch + "/tiers/" + form.dataset.tier + "/name", { name: name })
        .then(function (res) {
          if (!res.ok) { flash(res.body.message || say("tier_name_failed"), "error"); input.disabled = false; return; }
          swapTree(res.body.html);
        })
        .catch(function () { flash(say("network"), "error"); input.disabled = false; });
    };

    tree.addEventListener("input", function (e) {
      if (e.target.classList.contains("tier-name__input")) sizeTierName(e.target);
    });
    tree.addEventListener("keydown", function (e) {
      if (!e.target.classList.contains("tier-name__input")) return;
      if (e.key === "Escape") {
        e.preventDefault();
        e.target.value = e.target.defaultValue;
        sizeTierName(e.target);
        e.target.blur();
      }
    });
    tree.addEventListener("submit", function (e) {
      var form = e.target.closest("[data-tier-name]");
      if (!form) return;
      e.preventDefault();
      form.querySelector(".tier-name__input").blur();   // blur saves, once
    });
    tree.addEventListener("focusout", function (e) {
      var form = e.target.closest && e.target.closest("[data-tier-name]");
      if (form && e.target.classList.contains("tier-name__input") && !e.target.disabled) saveTierName(form);
    });
  }

  // ── Quick add ─────────────────────────────────────────────────────────
  // A tier's "+" and the "New tier" link open a box in place: type a title,
  // press Enter, and the machination is added with one point and the box
  // stays open for the next. Escape, or leaving it empty, closes it. A
  // modified click still follows the link to the full form.
  if (tree) {
    var quickBusy = false;

    var closeQuick = function () {
      var open = tree.querySelector(".quick-add");
      if (!open) return;
      var hidden = tree.querySelector("[data-quick-hidden]");
      if (hidden) { hidden.hidden = false; hidden.removeAttribute("data-quick-hidden"); }
      open.remove();
    };

    var openQuick = function (anchor) {
      closeQuick();
      var spot = anchor.closest("[data-tier]");
      if (!spot) return;
      var branch = spot.dataset.branch, tier = spot.dataset.tier;
      var form = document.createElement("form");
      form.className = "quick-add";
      var input = document.createElement("input");
      input.className = "input input--sm";
      input.maxLength = 120;
      input.placeholder = say("quick_placeholder");
      input.setAttribute("aria-label", say("quick_placeholder"));
      form.appendChild(input);
      if (anchor.classList.contains("tile--add")) {
        spot.parentNode.insertBefore(form, spot.nextSibling);
      } else {
        anchor.parentNode.insertBefore(form, anchor);
      }
      anchor.hidden = true;
      anchor.setAttribute("data-quick-hidden", "");
      input.focus();

      input.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { e.preventDefault(); closeQuick(); }
      });
      input.addEventListener("blur", function () {
        setTimeout(function () {
          if (!quickBusy && form.isConnected && !input.value.trim()) closeQuick();
        }, 150);
      });
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var title = input.value.trim();
        if (!title) { closeQuick(); return; }
        if (quickBusy) return;
        quickBusy = true;
        input.disabled = true;
        post("/schemes/" + branch + "/machinations/quick", { title: title, tier: Number(tier) })
          .then(function (res) {
            if (!res.ok) {
              flash(res.body.message || say("network"), "error");
              input.disabled = false;
              input.focus();
              return;
            }
            swapTree(res.body.html);
            updateStats(res.body);
            var added = tree.querySelector('[data-task="' + res.body.task + '"]');
            if (added) added.classList.add("is-flash");
            var again = tree.querySelector('.tier__row[data-branch="' + branch + '"][data-tier="' + tier + '"] .tile--add');
            if (again) openQuick(again);
          })
          .catch(function () { flash(say("network"), "error"); input.disabled = false; })
          .finally(function () { quickBusy = false; });
      });
    };

    tree.addEventListener("click", function (e) {
      var anchor = e.target.closest(".tile--add, .tier-add[data-tier]");
      if (!anchor || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      openQuick(anchor);
    });
  }

  // ── How a plot works ──────────────────────────────────────────────────
  // Shown until it is closed once in this browser. Storage can be missing
  // or refuse (private windows), in which case it simply shows each time.
  var guide = document.getElementById("guide");
  if (guide) {
    var seen = false;
    // ?guide=1 (replaying the first visit) shows it again, as if never closed.
    if (guide.hasAttribute("data-guide-force")) {
      try { localStorage.removeItem("guide-seen"); } catch (e) { /* not kept */ }
    }
    try { seen = localStorage.getItem("guide-seen") === "1"; } catch (e) { /* not kept */ }
    guide.hidden = seen;
    guide.addEventListener("click", function (e) {
      if (!e.target.closest("[data-guide-close]")) return;
      guide.hidden = true;
      try { localStorage.setItem("guide-seen", "1"); } catch (err) { /* not kept */ }
    });
    var reopen = document.querySelector("[data-guide-open]");
    if (reopen) reopen.addEventListener("click", function () {
      guide.hidden = false;
      guide.scrollIntoView({ block: "nearest" });
    });
  }

  // ── Flashes ───────────────────────────────────────────────────────────
  Array.prototype.forEach.call(document.querySelectorAll(".flash"), function (el) {
    setTimeout(function () { el.remove(); }, 4500);
  });
})();

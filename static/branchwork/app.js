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
    drawThreads();
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
    project: { handle: ".prow", zone: "[data-focus-zone]" },
    thread: { handle: ".tile__thread", zone: ".tile[data-task]" }
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
      id: handle.dataset.idea || handle.dataset.project || handle.dataset.threadFrom,
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
    } else if (moving.kind === "thread") {
      threadTasks(moving.id, zone.dataset.task);
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
    Array.prototype.forEach.call(svg.querySelectorAll("path[data-from]"), function (path) {
      var fromTile = tileOf(path.dataset.from), toTile = tileOf(path.dataset.to);
      if (!fromTile || !toTile) { path.removeAttribute("d"); return; }
      var a = boxOf(fromTile.querySelector(".tile__box"));
      var b = boxOf(toTile.querySelector(".tile__box"));
      var aRow = fromTile.closest(".tier__row"), bRow = toTile.closest(".tier__row");
      var aCol = fromTile.closest(".col"), bCol = toTile.closest(".col");
      var toTheRight = b.cx >= a.cx;
      // Arrows leave and arrive at a tile's side: the plate and the label sit
      // under it, and running through those reads as a mistake.
      var edgeA = toTheRight ? a.right : a.left;
      var edgeB = toTheRight ? b.left : b.right;
      var outA = toTheRight ? 1 : -1;
      var sameRow = aRow === bRow || Math.abs(boxOf(aRow).top - boxOf(bRow).top) < 4;
      var route = {
        path: path, a: a, b: b,
        leaves: path.dataset.from + (toTheRight ? ":right" : ":left"),
        arrives: path.dataset.to + (toTheRight ? ":left" : ":right")
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
    });
  }

  function threadTasks(fromId, toId) {
    if (!fromId || !toId || String(fromId) === String(toId)) return;
    post("/tasks/" + fromId + "/threads", { to: Number(toId) })
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

  // ── Flashes ───────────────────────────────────────────────────────────
  Array.prototype.forEach.call(document.querySelectorAll(".flash"), function (el) {
    setTimeout(function () { el.remove(); }, 4500);
  });
})();

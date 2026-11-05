// The walkthrough: pop-ups that point at one thing at a time while a new
// account builds its first plot. Signing up lands on /?tour=1, which starts
// it; Account → Walkthrough → Replay starts it again.
//
// Each step names the result it is waiting for (the plot exists, it has a
// scheme, a machination, a scored point) and moves on once the page shows
// it, so forms, quick add and the back button need no special handling. The
// last few steps only explain, and move on with Next. Progress is kept in
// localStorage so it survives page loads; without storage it lasts a page.
(function () {
  "use strict";

  var COPY = window.TOUR_COPY || {};
  var STEP = "tour-step", PLOT = "tour-plot", FORM = "tour-form";

  var memory = {};
  function get(k) {
    try { return localStorage.getItem(k); } catch (e) { return memory.hasOwnProperty(k) ? memory[k] : null; }
  }
  function set(k, v) {
    try { localStorage.setItem(k, v); } catch (e) { memory[k] = v; }
  }
  function drop(k) {
    try { localStorage.removeItem(k); } catch (e) { delete memory[k]; }
  }

  function say(key, values) {
    var text = COPY[key] || "";
    return text.replace(/\{(\w+)\}/g, function (whole, name) {
      return values && values[name] !== undefined ? values[name] : whole;
    });
  }

  // ?tour=1 starts from the top, and leaves the address clean behind it.
  var params = new URLSearchParams(location.search);
  if (params.get("tour") === "1") {
    set(STEP, "0"); drop(PLOT); drop(FORM);
    params.delete("tour");
    var rest = params.toString();
    history.replaceState(null, "", location.pathname + (rest ? "?" + rest : "") + location.hash);
  }
  if (get(STEP) === null) return;

  // The plot guide says the same things; it waits until the walkthrough ends.
  var guide = document.getElementById("guide");
  if (guide) guide.hidden = true;

  var path = location.pathname;
  var tree = document.getElementById("tree");
  var onTree = path.match(/^\/plots\/(\d+)$/);
  var onSchemeForm = path.match(/^\/plots\/(\d+)\/schemes\/new$/);
  var touch = window.matchMedia && window.matchMedia("(hover: none)").matches;

  function q(sel) { return document.querySelector(sel); }
  function shown(el) { return !!el && !el.hidden && el.getClientRects().length > 0; }
  function first(sels) {
    for (var i = 0; i < sels.length; i++) {
      var all = document.querySelectorAll(sels[i]);
      for (var j = 0; j < all.length; j++) if (shown(all[j])) return all[j];
    }
    return null;
  }
  function count(sel) { return tree ? tree.querySelectorAll(sel).length : 0; }
  // The plot made during the walkthrough, so another plot never stands in.
  function tourTree() { return !!(onTree && tree && get(PLOT) === onTree[1]); }

  var STEPS = [
    { // Start a plot, then name it. Blank, so the next step builds a scheme.
      done: function () {
        if (onTree && get(FORM) === "1") {
          if (get(PLOT) === null) set(PLOT, onTree[1]);
          return true;
        }
        return false;
      },
      view: function () {
        if (path === "/") {
          return { target: first([".empty a[href='/plots/new']", ".topbar a[href='/plots/new']"]),
                   title: "new_plot_title", body: "new_plot_body" };
        }
        if (path === "/plots/new") {
          if (get(FORM) !== "1") {
            var blank = q("input[name=starter][value=blank]");
            if (blank) blank.checked = true;
            set(FORM, "1");
          }
          return { target: q("#name"), title: "plot_form_title", body: "plot_form_body" };
        }
        return null;
      }
    },
    { // Add a scheme, then name it.
      done: function () { return tourTree() && count(".col[data-branch]") > 0; },
      view: function () {
        if (tourTree()) return { target: q("#tree .col--add"), title: "add_scheme_title", body: "add_scheme_body" };
        if (onSchemeForm && get(PLOT) === onSchemeForm[1]) {
          return { target: q("#name"), title: "scheme_form_title", body: "scheme_form_body" };
        }
        return null;
      }
    },
    { // Machinations, typed straight into a tier.
      done: function () { return tourTree() && count(".tile[data-task]") > 0; },
      view: function () {
        return tourTree() ? { target: first(["#tree .quick-add", "#tree .tier-add[data-tier]"]),
                              title: "add_machination_title", body: "add_machination_body" } : null;
      }
    },
    { // A point.
      done: function () { return tourTree() && count(".tile--full") > 0; },
      view: function () {
        return tourTree() ? { target: q("#tree .tile--live[data-task] .tile__box"), title: "score_title",
                              body: touch ? "score_body_touch" : "score_body" } : null;
      }
    },
    { info: true, view: function () {
        return tourTree() ? { target: first(["#tree .tier-add[data-tier]"]), title: "tiers_title",
                              body: "tiers_body", values: { gate: tree.dataset.gate || 3 } } : null;
      } },
    { info: true, view: function () {
        return tourTree() ? { target: q("#tree .tier-add--ultimate"), title: "ultimate_title", body: "ultimate_body" } : null;
      } },
    { info: true, view: function () {
        return tourTree() ? { target: q("#tree .col--add"), title: "more_title", body: "more_body" } : null;
      } },
    { info: true, last: true, view: function () {
        return tourTree() ? { target: null, title: "done_title", body: "done_body" } : null;
      } }
  ];

  // ── The card ────────────────────────────────────────────────────────────
  var card = document.createElement("div");
  card.className = "tour";
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-labelledby", "tour-title");
  card.hidden = true;
  card.innerHTML =
    '<p class="tour__count"></p>' +
    '<h2 class="tour__title" id="tour-title"></h2>' +
    '<p class="tour__body"></p>' +
    '<div class="tour__actions">' +
    '<button type="button" class="link-btn tour__skip"></button>' +
    '<button type="button" class="btn btn--primary btn--sm tour__next"></button>' +
    "</div>";
  document.body.appendChild(card);
  card.querySelector(".tour__skip").textContent = say("skip");

  var ringed = null, shownKey = null;

  function ring(el) {
    if (ringed === el) return;
    if (ringed) ringed.classList.remove("tour-ring");
    ringed = el;
    if (el) el.classList.add("tour-ring");
  }

  // Room under the page for the card, so nothing ends up stuck beneath it.
  function pad(on) {
    document.body.style.paddingBottom = on ? (card.offsetHeight + 32) + "px" : "";
  }

  function finish() {
    ring(null);
    pad(false);
    card.remove();
    drop(STEP); drop(PLOT); drop(FORM);
    // The walkthrough covered what the guide says.
    try { localStorage.setItem("guide-seen", "1"); } catch (e) { /* not kept */ }
    if (observer) observer.disconnect();
  }

  function overlaps(a, b) {
    return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  }

  // A corner of the screen, away from what it points at.
  function place(target) {
    card.classList.remove("tour--left", "tour--top");
    if (!target) return;
    var t = target.getBoundingClientRect();
    if (!overlaps(card.getBoundingClientRect(), t)) return;
    card.classList.add("tour--left");
    if (!overlaps(card.getBoundingClientRect(), t)) return;
    card.classList.remove("tour--left");
    card.classList.add("tour--top");
  }

  function render(index, step, view) {
    var key = index + ":" + view.title;
    if (key !== shownKey) {
      shownKey = key;
      card.querySelector(".tour__count").textContent = say("count", { n: index + 1, total: STEPS.length });
      card.querySelector(".tour__title").textContent = say(view.title);
      card.querySelector(".tour__body").textContent = say(view.body, view.values);
      var next = card.querySelector(".tour__next");
      next.hidden = !step.info;
      next.textContent = step.last ? say("finish") : say("next");
      card.querySelector(".tour__skip").hidden = !!step.last;
      if (view.target) {
        var r = view.target.getBoundingClientRect();
        if (r.top < 64 || r.bottom > window.innerHeight - 24) {
          view.target.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
        }
      }
    }
    card.hidden = false;
    pad(true);
    ring(view.target);
    place(view.target);
  }

  function evaluate() {
    var stored = parseInt(get(STEP), 10);
    if (isNaN(stored)) { finish(); return; }
    var index = stored;
    while (index < STEPS.length && !STEPS[index].info && STEPS[index].done()) index++;
    if (index >= STEPS.length) { finish(); return; }
    if (index !== stored) set(STEP, String(index));
    var step = STEPS[index];
    var view = step.view();
    if (!view) { card.hidden = true; pad(false); ring(null); return; }
    render(index, step, view);
  }

  card.addEventListener("click", function (e) {
    if (e.target.closest(".tour__skip")) { finish(); return; }
    if (e.target.closest(".tour__next")) {
      var index = parseInt(get(STEP), 10) || 0;
      if (STEPS[index] && STEPS[index].last) { finish(); return; }
      set(STEP, String(index + 1));
      evaluate();
    }
  });

  // The tree changes without a reload (points, quick add), so watch it.
  var pending = null;
  function later() {
    if (pending) return;
    pending = requestAnimationFrame(function () { pending = null; evaluate(); });
  }
  var observer = tree && window.MutationObserver ? new MutationObserver(later) : null;
  if (observer) observer.observe(tree, { childList: true, subtree: true });
  window.addEventListener("resize", later);

  evaluate();
})();

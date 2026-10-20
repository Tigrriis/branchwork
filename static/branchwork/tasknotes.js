// The machination form's notes: the same encrypted notes as the Notes page,
// filed in this machination's folder. Each row arrives sealed and is opened
// here into its title and first line once the notes key is unlocked, from an
// earlier page or from the small unlock row. Editing happens on the Notes
// page, where each row leads.
(function () {
  "use strict";

  var box = document.querySelector("[data-task-notes]");
  var data = document.getElementById("vault-data");
  var Vault = window.Vault;
  var say = (window.BRANCHWORK || {}).say || function (key) { return key; };
  if (!box || !data || !Vault || !Vault.supported) return;
  Vault.configure(JSON.parse(data.textContent));

  var rows = Array.prototype.slice.call(box.querySelectorAll(".tnote"));
  var stamp = window.Intl && Intl.DateTimeFormat
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }) : null;
  Array.prototype.forEach.call(box.querySelectorAll("[data-when]"), function (el) {
    var d = new Date(el.dataset.when);
    if (!isNaN(d)) el.textContent = stamp ? stamp.format(d) : d.toLocaleString();
  });

  // The same order the Notes page's Sort picker was last left on.
  function sortRows() {
    var mode;
    try { mode = localStorage.getItem("notes-sort") || "name"; } catch (e) { mode = "name"; }
    var list = box.querySelector(".tnotes__list");
    if (!list) return;
    var title = function (row) { return row.querySelector(".tnote__title").textContent; };
    var byName = function (a, b) { return title(a).localeCompare(title(b), undefined, { sensitivity: "base", numeric: true }); };
    var byCreated = function (a, b) {
      var x = a.dataset.created, y = b.dataset.created;
      return x < y ? -1 : x > y ? 1 : byName(a, b);
    };
    var order = mode === "newest" ? function (a, b) { return byCreated(b, a); } : mode === "oldest" ? byCreated : byName;
    rows.slice().sort(order).forEach(function (row) { list.appendChild(row.parentNode); });
  }
  var unlock = box.querySelector("[data-tnotes-unlock]");

  // The first line with words in it, without the markdown around them.
  function firstLine(body) {
    var lines = body.split("\n").map(function (line) {
      return line.replace(/^[\s>#*+-]*(\d+[.)]\s*)?(\[[ xX]\]\s*)?/, "").trim();
    }).filter(Boolean);
    return (lines[0] || "").slice(0, 160);
  }

  function open() {
    if (unlock) unlock.hidden = true;
    // Text the old notes box held becomes a note first, then the list shows it.
    return Vault.absorb().then(function (made) {
      if (made) { window.location.reload(); return; }
      return Promise.all(rows.map(function (row) {
        var title = row.querySelector(".tnote__title"), snippet = row.querySelector(".tnote__snippet");
        return Promise.all([Vault.decrypt(row.dataset.sealedTitle, "title"), Vault.decrypt(row.dataset.sealedBody, "body")])
          .then(function (both) {
            title.textContent = both[0];
            snippet.textContent = firstLine(both[1]);
          }, function () {
            title.textContent = say("note_unreadable");
            row.classList.add("is-broken");
          });
      })).then(sortRows);
    });
  }

  Vault.restore().then(function (ok) {
    if (ok) open();
    else if (unlock) unlock.hidden = false;
  });

  if (unlock) {
    var password = unlock.querySelector("[data-tnotes-password]");
    var button = unlock.querySelector("[data-tnotes-open]");
    var status = unlock.querySelector("[data-vault-status]");
    var tell = function (text, bad) { status.textContent = text; status.classList.toggle("is-failed", !!bad); };
    var go = function () {
      if (!password.value) return;
      button.disabled = true;
      tell(say("vault_unlocking"));
      Vault.unlock(password.value)
        .then(function () { password.value = ""; tell(""); return open(); },
              function () { tell(say("vault_wrong"), true); password.select(); })
        .then(function () { button.disabled = false; });
    };
    button.addEventListener("click", go);
    // Enter here would otherwise submit the machination's form around it.
    password.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); go(); }
    });
  }
})();

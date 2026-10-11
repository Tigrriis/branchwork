// Notes page script: the explorer, the editor, and a small markdown reader.
//
// The tree's script swaps in HTML the server rendered. Notes are the
// exception, because the server cannot read them: every title and body is
// sealed with the notes key (vault.js) before it is sent and arrives back
// sealed. So this page decrypts, and then does what the server cannot:
// renders the markdown, and sorts and searches the titles.
(function () {
  "use strict";

  var shared = window.BRANCHWORK || {};
  var say = shared.say || function (key) { return key; };
  var flash = shared.flash || function () {};
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  function remember(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (e) { /* private window: it lasts this page */ }
  }
  function recall(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  // ── Markdown ──────────────────────────────────────────────────────────
  // The subset a notebook needs, Obsidian's way where it differs: a single
  // line break is a break, [[Title]] links to another note, - [ ] is a
  // checkbox, > [!note] is a callout, #word is a tag. Everything is escaped
  // first and only these shapes become markup, so a note cannot inject any.
  var md = (function () {
    var ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    function esc(text) { return String(text).replace(/[&<>"']/g, function (c) { return ESC[c]; }); }

    // Web, mail and in-page addresses, and relative ones. Anything else
    // with a scheme (javascript:, data:) stays as text.
    function safeUrl(url) {
      var u = url.trim();
      if (/^(https?:|mailto:)/i.test(u)) return u;
      if (/^[a-z][a-z0-9+.-]*:/i.test(u)) return null;
      return u;
    }

    var LIST = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
    var TASK = /^\[([ xX])\]\s+(.*)$/;
    var FENCE = /^\s*(`{3,}|~{3,})\s*([\w+#.-]*)/;
    var HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
    var RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
    var QUOTE = /^\s*>/;
    var TABLE_RULE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

    function width(lead) { return lead.replace(/\t/g, "    ").length; }

    function inline(src, ctx) {
      var slots = [];
      function keep(html) { slots.push(html); return "\u0000" + (slots.length - 1) + "\u0000"; }
      var s = String(src).replace(/\u0000/g, "");

      s = s.replace(/`([^`\n]+)`/g, function (m, code) { return keep("<code>" + esc(code) + "</code>"); });
      s = s.replace(/\[\[([^\]|\n]+)(?:\|([^\]\n]+))?\]\]/g, function (m, target, label) {
        return keep(ctx.wiki(target.trim(), (label || target).trim()));
      });
      s = s.replace(/!\[([^\]\n]*)\]\(\s*<?([^)\s>]+)>?\s*\)/g, function (m, alt, url) {
        var u = safeUrl(url);
        if (!u || !/^https?:/i.test(u)) return m;
        return keep('<img src="' + esc(u) + '" alt="' + esc(alt) + '" loading="lazy">');
      });
      s = s.replace(/\[([^\]\n]+)\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"\n]*")?\s*\)/g, function (m, text, url) {
        var u = safeUrl(url);
        if (!u) return m;
        return keep('<a href="' + esc(u) + '" target="_blank" rel="noopener noreferrer">' + inline(text, ctx) + "</a>");
      });
      s = s.replace(/\bhttps?:\/\/[^\s<>"]*[^\s<>".,:;!?'")\]]/g, function (url) {
        return keep('<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(url) + "</a>");
      });

      s = esc(s)
        .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[^\w])__(?=\S)([\s\S]*?\S)__(?!\w)/g, "$1<strong>$2</strong>")
        .replace(/\*(?=\S)([\s\S]*?\S)\*/g, "<em>$1</em>")
        .replace(/(^|[^\w])_(?=\S)([\s\S]*?\S)_(?!\w)/g, "$1<em>$2</em>")
        .replace(/~~(?=\S)([\s\S]*?\S)~~/g, "<del>$1</del>")
        .replace(/==(?=\S)([\s\S]*?\S)==/g, "<mark>$1</mark>")
        .replace(/(^|\s)#([A-Za-z][\w\/-]*)/g, '$1<span class="md-tag">#$2</span>')
        .replace(/\n/g, "<br>");
      return s.replace(/\u0000(\d+)\u0000/g, function (m, i) { return slots[Number(i)]; });
    }

    function startsBlock(line, next) {
      return FENCE.test(line) || HEADING.test(line) || RULE.test(line) || QUOTE.test(line) ||
        LIST.test(line) || (line.indexOf("|") !== -1 && next !== undefined && TABLE_RULE.test(next));
    }

    function cells(row) {
      return row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|")
        .map(function (cell) { return cell.trim(); });
    }

    function list(lines, i, ctx) {
      var first = lines[i].match(LIST);
      var indent = width(first[1]);
      var ordered = /\d/.test(first[2]);
      var items = [], item = null;
      while (i < lines.length) {
        var line = lines[i];
        var m = line.match(LIST);
        if (!m) {
          if (!line.trim()) {
            // A blank line ends the list unless more of it follows.
            var k = i + 1;
            while (k < lines.length && !lines[k].trim()) k++;
            var after = k < lines.length && lines[k].match(LIST);
            if (after && width(after[1]) >= indent) { i = k; continue; }
            break;
          }
          if (item && width(line.match(/^\s*/)[0]) > indent) {
            item.text += "\n" + line.trim();
            i++;
            continue;
          }
          break;
        }
        var here = width(m[1]);
        if (here < indent || (here === indent && /\d/.test(m[2]) !== ordered)) break;
        if (here > indent && item) {
          var sub = list(lines, i, ctx);
          item.children += sub.html;
          i = sub.next;
          continue;
        }
        var task = m[3].match(TASK);
        item = { text: task ? task[2] : m[3], children: "", task: !!task,
                 checked: !!task && task[1] !== " ", box: task ? ctx.boxes++ : -1 };
        items.push(item);
        i++;
      }
      var tag = ordered ? "ol" : "ul";
      var start = ordered && parseInt(first[2], 10) !== 1 ? ' start="' + parseInt(first[2], 10) + '"' : "";
      var html = "<" + tag + start + ">";
      items.forEach(function (it) {
        if (it.task) {
          html += '<li class="md-task' + (it.checked ? " is-done" : "") + '"><label><input type="checkbox" data-box="' +
            it.box + '"' + (it.checked ? " checked" : "") + "> <span>" + inline(it.text, ctx) + "</span></label>" +
            it.children + "</li>";
        } else {
          html += "<li>" + inline(it.text, ctx) + it.children + "</li>";
        }
      });
      return { html: html + "</" + tag + ">", next: i };
    }

    function blocks(src, ctx) {
      var lines = src.split("\n");
      var out = [];
      var i = 0;
      while (i < lines.length) {
        var line = lines[i];
        if (!line.trim()) { i++; continue; }

        var fence = line.match(FENCE);
        if (fence) {
          var code = [];
          i++;
          while (i < lines.length && lines[i].trim().indexOf(fence[1]) !== 0) code.push(lines[i++]);
          i++;
          out.push("<pre><code" + (fence[2] ? ' class="lang-' + esc(fence[2]) + '"' : "") + ">" +
                   esc(code.join("\n")) + "</code></pre>");
          continue;
        }
        var h = line.match(HEADING);
        if (h) {
          out.push("<h" + h[1].length + ">" + inline(h[2], ctx) + "</h" + h[1].length + ">");
          i++;
          continue;
        }
        if (RULE.test(line)) { out.push("<hr>"); i++; continue; }
        if (QUOTE.test(line)) {
          var quoted = [];
          while (i < lines.length && QUOTE.test(lines[i])) quoted.push(lines[i++].replace(/^\s*>\s?/, ""));
          var callout = quoted[0].match(/^\[!(\w+)\][+-]?\s*(.*)$/);
          if (callout) {
            var kind = callout[1].toLowerCase();
            out.push('<div class="md-callout md-callout--' + esc(kind) + '"><div class="md-callout__title">' +
                     inline(callout[2] || kind.charAt(0).toUpperCase() + kind.slice(1), ctx) + "</div>" +
                     blocks(quoted.slice(1).join("\n"), ctx) + "</div>");
          } else {
            out.push("<blockquote>" + blocks(quoted.join("\n"), ctx) + "</blockquote>");
          }
          continue;
        }
        if (line.indexOf("|") !== -1 && i + 1 < lines.length && TABLE_RULE.test(lines[i + 1])) {
          var head = cells(line);
          var aligns = cells(lines[i + 1]).map(function (c) {
            return /^:-+:$/.test(c) ? "center" : /-:$/.test(c) ? "right" : "";
          });
          var cell = function (tag, text, n) {
            return "<" + tag + (aligns[n] ? ' style="text-align:' + aligns[n] + '"' : "") + ">" +
                   inline(text, ctx) + "</" + tag + ">";
          };
          var html = '<div class="md-table"><table><thead><tr>' +
            head.map(function (c, n) { return cell("th", c, n); }).join("") + "</tr></thead><tbody>";
          i += 2;
          while (i < lines.length && lines[i].trim() && lines[i].indexOf("|") !== -1) {
            var row = cells(lines[i++]);
            html += "<tr>" + head.map(function (c, n) { return cell("td", row[n] || "", n); }).join("") + "</tr>";
          }
          out.push(html + "</tbody></table></div>");
          continue;
        }
        if (LIST.test(line)) {
          var made = list(lines, i, ctx);
          out.push(made.html);
          i = made.next;
          continue;
        }
        var para = [line];
        i++;
        while (i < lines.length && lines[i].trim() && !startsBlock(lines[i], lines[i + 1])) para.push(lines[i++]);
        out.push("<p>" + inline(para.join("\n"), ctx) + "</p>");
      }
      return out.join("\n");
    }

    return {
      // ``wiki(target, label)`` turns a [[link]] into an anchor.
      render: function (src, wiki) {
        return blocks(String(src || "").replace(/\r\n?/g, "\n"), { wiki: wiki, boxes: 0 });
      },
      esc: esc,
      // Flip the nth checkbox in the source, counting as the reader does:
      // fenced code is skipped, quoted checkboxes count.
      toggleBox: function (src, n) {
        var lines = String(src).replace(/\r\n?/g, "\n").split("\n");
        var fence = null, seen = 0;
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          var f = line.replace(/^(\s*>)*/, "").match(FENCE);
          if (fence) {
            if (line.replace(/^(\s*>)*/, "").trim().indexOf(fence) === 0) fence = null;
            continue;
          }
          if (f) { fence = f[1]; continue; }
          var m = line.match(/^((?:\s*>)*\s*(?:[-*+]|\d{1,9}[.)])\s+\[)([ xX])(\]\s)/);
          if (!m) continue;
          if (seen++ === n) {
            lines[i] = m[1] + (m[2] === " " ? "x" : " ") + m[3] + line.slice(m[0].length);
            return lines.join("\n");
          }
        }
        return null;
      }
    };
  })();

  // ── Explorer ──────────────────────────────────────────────────────────
  var Vault = window.Vault;
  var explorer = document.getElementById("note-explorer");
  var filter = document.querySelector("[data-nx-filter]");
  var emptyToggle = document.querySelector("[data-nx-empty]");
  var foldAll = document.querySelector("[data-nx-fold]");
  var dataEl = document.getElementById("note-data");
  var state = dataEl ? JSON.parse(dataEl.textContent) : null;

  function folders() { return Array.prototype.slice.call(explorer.querySelectorAll("details[data-folder]")); }
  function rowOf(id) { return explorer && explorer.querySelector('.nx-note[data-note="' + id + '"]'); }

  // Titles arrive sealed. Open them, then put each folder's notes in order,
  // which the server cannot do for want of being able to read them.
  function openTitles() {
    if (!explorer) return Promise.resolve();
    var rows = Array.prototype.slice.call(explorer.querySelectorAll(".nx-note[data-sealed-title]"));
    return Promise.all(rows.map(function (row) {
      return Vault.decrypt(row.dataset.sealedTitle, "title").then(function (title) {
        row.dataset.noteTitle = title;
        row.querySelector(".nx-note__title").textContent = title;
      }, function () {
        row.dataset.noteTitle = "";
        row.classList.add("is-broken");
        row.querySelector(".nx-note__title").textContent = say("note_unreadable");
      }).then(function () { row.removeAttribute("data-sealed-title"); });
    })).then(sortTitles);
  }

  function sortTitles() {
    Array.prototype.forEach.call(explorer.querySelectorAll(".nx__items"), function (box) {
      var rows = Array.prototype.filter.call(box.children, function (el) { return el.classList.contains("nx-note"); });
      rows.sort(function (a, b) {
        return (a.dataset.noteTitle || "").localeCompare(b.dataset.noteTitle || "", undefined, { sensitivity: "base", numeric: true });
      });
      rows.forEach(function (row) { box.appendChild(row); });
    });
  }

  // While a filter is typed, folders open to show what matches; clearing it
  // puts them back the way they were.
  var openBeforeFilter = null;
  function applyFilter() {
    if (!explorer || !filter) return;
    var q = filter.value.trim().toLowerCase();
    var notes = explorer.querySelectorAll(".nx-note");
    if (!q) {
      Array.prototype.forEach.call(notes, function (n) { n.hidden = false; });
      folders().forEach(function (f) {
        f.hidden = false;
        if (openBeforeFilter) f.open = openBeforeFilter.indexOf(f.dataset.folder) !== -1;
      });
      openBeforeFilter = null;
      explorer.querySelector("[data-nx-none]").hidden = true;
      explorer.classList.remove("nx--filtering");
      return;
    }
    if (!openBeforeFilter) {
      openBeforeFilter = folders().filter(function (f) { return f.open; })
        .map(function (f) { return f.dataset.folder; });
    }
    explorer.classList.add("nx--filtering");
    var hits = 0;
    Array.prototype.forEach.call(notes, function (n) {
      var hit = (n.dataset.noteTitle || "").toLowerCase().indexOf(q) !== -1;
      n.hidden = !hit;
      if (hit) hits++;
    });
    // Innermost first, so a scheme sees whether its machinations matched.
    folders().reverse().forEach(function (f) {
      var any = !!f.querySelector(".nx-note:not([hidden])");
      f.hidden = !any;
      f.open = any;
    });
    explorer.querySelector("[data-nx-none]").hidden = hits > 0;
  }

  function swapExplorer(html) {
    if (!explorer) return Promise.resolve();
    var wasOpen = folders().filter(function (f) { return f.open; }).map(function (f) { return f.dataset.folder; });
    explorer.innerHTML = html;
    folders().forEach(function (f) { if (wasOpen.indexOf(f.dataset.folder) !== -1) f.open = true; });
    // The server marks the note it just saved; the page knows which is open.
    Array.prototype.forEach.call(explorer.querySelectorAll(".nx-note"), function (row) {
      var open = !!state && String(state.id) === row.dataset.note;
      row.classList.toggle("is-current", open);
      if (open) row.setAttribute("aria-current", "page"); else row.removeAttribute("aria-current");
    });
    return openTitles().then(function () {
      if (filter && filter.value.trim()) { openBeforeFilter = null; applyFilter(); }
    });
  }

  if (explorer) {
    if (filter) {
      filter.addEventListener("input", applyFilter);
      filter.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          var first = explorer.querySelector(".nx-note:not([hidden])");
          if (first) { e.preventDefault(); first.click(); }
        } else if (e.key === "Escape") {
          filter.value = "";
          applyFilter();
        }
      });
    }
    var showHideEmpty = function (hide) {
      explorer.classList.toggle("nx--hide-empty", hide);
      if (emptyToggle) emptyToggle.setAttribute("aria-pressed", hide ? "true" : "false");
    };
    showHideEmpty(recall("notes-hide-empty") === "1");
    if (emptyToggle) {
      emptyToggle.addEventListener("click", function () {
        var hide = !explorer.classList.contains("nx--hide-empty");
        showHideEmpty(hide);
        remember("notes-hide-empty", hide ? "1" : null);
      });
    }
    if (foldAll) {
      foldAll.addEventListener("click", function () { folders().forEach(function (f) { f.open = false; }); });
    }
    var current = explorer.querySelector(".nx-note.is-current");
    if (current && current.scrollIntoView) current.scrollIntoView({ block: "nearest" });
  }

  // ── The open note ─────────────────────────────────────────────────────
  var titleEl = document.querySelector("[data-note-name]");
  var bodyEl = document.querySelector("[data-note-body]");
  var viewEl = document.querySelector("[data-note-view]");
  var statusEl = document.querySelector("[data-note-status]");
  var folderEl = document.querySelector("[data-note-folder]");
  var deleteForm = document.querySelector("[data-note-delete]");
  var modeButtons = document.querySelectorAll("[data-note-mode]");
  var titleSuffix = document.title.indexOf(" · ") !== -1 ? document.title.slice(document.title.indexOf(" · ")) : "";

  // Shared with the idle lock, which must not drop the key with a save owed.
  var editor = { pending: function () { return false; }, flush: function () { return Promise.resolve(); } };

  function setStatus(key, failed) {
    if (!statusEl) return;
    statusEl.textContent = say(key);
    statusEl.classList.toggle("is-failed", !!failed);
  }

  // [[Title]] goes to the note of that title, the open note's folder first;
  // a title with no note starts one there. The title rides in the #fragment,
  // which the browser keeps to itself, so it never reaches the server.
  function wikiLink(target, label) {
    var title = target.split("#")[0].trim();
    var key = title.toLowerCase();
    var rows = explorer ? Array.prototype.slice.call(explorer.querySelectorAll(".nx-note")) : [];
    var matches = rows.filter(function (r) { return (r.dataset.noteTitle || "").toLowerCase() === key; });
    var here = state && matches.filter(function (r) { return r.dataset.folder === state.folder; })[0];
    var hit = here || matches[0];
    if (hit) return '<a class="md-wiki" href="' + md.esc(hit.getAttribute("href")) + '">' + md.esc(label) + "</a>";
    var place = (state.folder || "plot").split(":");
    var url = state.new_url + (place[1] ? "?" + place[0] + "=" + place[1] : "") +
              "#title=" + encodeURIComponent(title);
    return '<a class="md-wiki is-missing" href="' + md.esc(url) + '">' + md.esc(label) + "</a>";
  }

  function draftTitle() {
    var m = window.location.hash.match(/^#title=(.*)$/);
    if (!m) return "";
    try { return decodeURIComponent(m[1]).slice(0, 200); } catch (e) { return ""; }
  }

  function startEditor(title, body) {
    titleEl.value = title;
    bodyEl.value = body;
    titleEl.disabled = bodyEl.disabled = false;
    if (state.id !== null) document.title = (title || state.untitled) + titleSuffix;

    var dirty = { title: false, body: false, folder: false };
    var saving = null;      // the save in flight, as a promise
    var again = false;      // something changed while it was in flight
    var timer = null;

    var pending = function () { return dirty.title || dirty.body || dirty.folder; };

    // A draft is only written once there is something in it: a pencil
    // followed by a change of mind leaves nothing behind.
    var worthCreating = function () { return titleEl.value.trim() !== "" || bodyEl.value.trim() !== ""; };

    // What to send, sealed. The fields are read before the sealing starts,
    // so typing meanwhile goes in the next save rather than being lost.
    var payload = function (fields) {
      var creating = state.id === null;
      var title = titleEl.value.trim() || state.untitled;
      var body = bodyEl.value;
      var out = {}, jobs = [];
      if (creating || fields.title) {
        jobs.push(Vault.encrypt(title, "title").then(function (s) { out.title = s; }));
      }
      if (creating || fields.body) {
        if (body.length > state.max_chars) return Promise.reject(new Error(say("note_too_long")));
        jobs.push(Vault.encrypt(body, "body").then(function (s) { out.body = s; }));
      }
      if (creating || fields.folder) out.folder = state.folder;
      return Promise.all(jobs).then(function () { return { data: out, title: title }; });
    };

    var send = function (url, data) {
      return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify(data),
        credentials: "same-origin"
      }).then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, body: j }; });
      });
    };

    var settle = function (res, title) {
      var made = state.id === null;
      state.id = res.id;
      state.save_url = res.save_url;
      state.folder = res.folder;
      if (made) {
        if (window.history && history.replaceState) history.replaceState(null, "", res.url);
        if (deleteForm) { deleteForm.action = res.delete_url; deleteForm.hidden = false; }
      }
      var relabel = function () {
        var row = rowOf(res.id);
        if (!row) return;
        row.dataset.noteTitle = title;
        row.querySelector(".nx-note__title").textContent = title;
      };
      if (res.explorer) swapExplorer(res.explorer).then(relabel); else relabel();
      document.title = title + titleSuffix;
    };

    var flush = function () {
      clearTimeout(timer);
      if (saving) { again = true; return saving; }
      if (!pending()) return Promise.resolve();
      if (state.id === null && !worthCreating()) return Promise.resolve();
      var url = state.id === null ? state.create_url : state.save_url;
      var sent = dirty;
      dirty = { title: false, body: false, folder: false };
      setStatus("note_saving");
      saving = payload(sent)
        .then(function (made) {
          return send(url, made.data).then(function (res) {
            if (!res.ok) throw new Error((res.body && res.body.message) || say("note_failed"));
            settle(res.body, made.title);
            setStatus(pending() ? "note_unsaved" : "note_saved");
          });
        })
        .catch(function (err) {
          // Whatever did not land is still to save.
          Object.keys(sent).forEach(function (k) { if (sent[k]) dirty[k] = true; });
          setStatus("note_failed", true);
          if (err && err.message) flash(err.message, "error");
        })
        .then(function () {
          saving = null;
          if (again) { again = false; return flush(); }
        });
      return saving;
    };
    editor = { pending: function () { return pending() || !!saving; }, flush: flush };

    var changed = function (field) {
      dirty[field] = true;
      Vault.touch();
      setStatus("note_unsaved");
      clearTimeout(timer);
      timer = setTimeout(flush, 700);
    };

    // ── Editing ──
    var grow = function () {
      bodyEl.style.height = "auto";
      bodyEl.style.height = bodyEl.scrollHeight + 2 + "px";
    };
    bodyEl.addEventListener("input", function () { grow(); changed("body"); });
    titleEl.addEventListener("input", function () { changed("title"); });
    titleEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); setMode("edit"); bodyEl.focus(); }
    });
    titleEl.addEventListener("blur", function () { if (pending()) flush(); });
    bodyEl.addEventListener("blur", function () { if (pending()) flush(); });

    if (folderEl) {
      folderEl.addEventListener("change", function () {
        state.folder = folderEl.value;
        if (state.id === null) return;   // a draft just remembers it
        dirty.folder = true;
        flush();
      });
    }

    var insert = function (text) {
      // execCommand keeps the edit on the undo stack; setRangeText where it is gone.
      if (!(document.execCommand && document.execCommand("insertText", false, text))) {
        bodyEl.setRangeText(text, bodyEl.selectionStart, bodyEl.selectionEnd, "end");
        bodyEl.dispatchEvent(new Event("input"));
      }
    };

    // Enter in a list carries the bullet, number or checkbox on to the next
    // line; Enter on an empty item ends the list.
    bodyEl.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" || e.shiftKey || e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
      var at = bodyEl.selectionStart;
      if (at !== bodyEl.selectionEnd) return;
      var start = bodyEl.value.lastIndexOf("\n", at - 1) + 1;
      var line = bodyEl.value.slice(start, at);
      var m = line.match(/^(\s*(?:>\s*)*)([-*+]|(\d{1,9})([.)]))(\s+)(\[[ xX]\]\s+)?(.*)$/);
      if (!m) return;
      var end = bodyEl.value.indexOf("\n", at);
      var rest = bodyEl.value.slice(at, end === -1 ? undefined : end);
      e.preventDefault();
      if (!m[7].trim() && !rest.trim()) {
        bodyEl.setSelectionRange(start, at);
        insert("");
        return;
      }
      var marker = m[3] ? (parseInt(m[3], 10) + 1) + m[4] : m[2];
      insert("\n" + m[1] + marker + m[5] + (m[6] ? "[ ] " : ""));
    });

    // ── Reading ──
    var mode = "edit";
    var render = function () {
      viewEl.innerHTML = bodyEl.value.trim() ? md.render(bodyEl.value, wikiLink)
        : '<p class="muted">' + md.esc(bodyEl.getAttribute("placeholder") || "") + "</p>";
    };
    var setMode = function (next, keep) {
      mode = next;
      if (mode === "read") render();
      viewEl.hidden = mode !== "read";
      bodyEl.hidden = mode === "read";
      Array.prototype.forEach.call(modeButtons, function (b) {
        b.classList.toggle("is-active", b.dataset.noteMode === mode);
        b.setAttribute("aria-pressed", b.dataset.noteMode === mode ? "true" : "false");
      });
      if (mode === "edit") grow();
      if (keep) remember("notes-mode", mode);
    };
    Array.prototype.forEach.call(modeButtons, function (b) {
      b.addEventListener("click", function () {
        setMode(b.dataset.noteMode, true);
        if (mode === "edit") bodyEl.focus();
      });
    });

    // A ticked box in the reading view is ticked in the markdown too.
    viewEl.addEventListener("change", function (e) {
      var box = e.target.closest("input[data-box]");
      if (!box) return;
      var next = md.toggleBox(bodyEl.value, Number(box.dataset.box));
      if (next === null) return;
      bodyEl.value = next;
      changed("body");
      render();
    });
    viewEl.addEventListener("dblclick", function (e) {
      if (e.target.closest("a, input, label")) return;
      setMode("edit", true);
      bodyEl.focus();
    });

    document.addEventListener("keydown", function (e) {
      if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
      var key = e.key.toLowerCase();
      if (key === "e") {
        e.preventDefault();
        setMode(mode === "edit" ? "read" : "edit", true);
        if (mode === "edit") bodyEl.focus();
      } else if (key === "s") {
        e.preventDefault();
        flush();
      }
    });

    // A new note opens for writing, and so does one with nothing in it yet;
    // otherwise it opens the way the last one was left.
    var empty = state.id === null || !bodyEl.value.trim();
    setMode(empty ? "edit" : (recall("notes-mode") || "read"));
    if (state.id === null) {
      if (titleEl.value) bodyEl.focus(); else titleEl.focus();
    }
  }

  // Following a link with changes unsaved saves them first. Closing the tab
  // or going back cannot wait for sealing and sending, so those ask first.
  document.addEventListener("click", function (e) {
    var link = e.target.closest && e.target.closest("a[href]");
    if (!link || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    if (link.target === "_blank" || !editor.pending()) return;
    e.preventDefault();
    var go = function () { window.location.href = link.href; };
    editor.flush().then(go, go);
  });
  window.addEventListener("beforeunload", function (e) {
    if (!editor.pending()) return;
    editor.flush();
    e.preventDefault();
    e.returnValue = "";
  });

  // ── Moving ────────────────────────────────────────────────────────────
  // A note dropped on a folder in the explorer (app.js does the dragging).
  // Where a note sits is not secret, so this sends nothing sealed.
  document.addEventListener("note-drop", function (e) {
    var id = String(e.detail.id), folder = e.detail.folder;
    var row = rowOf(id);
    if (!row || row.dataset.folder === folder || !Vault.alive()) return;
    shared.post("/notes/" + id, { folder: folder }).then(function (res) {
      if (!res.ok) { flash(res.body.message || say("note_move_failed"), "error"); return; }
      if (state && String(state.id) === id) {
        state.folder = res.body.folder;
        if (folderEl) folderEl.value = res.body.folder;
      }
      return swapExplorer(res.body.explorer).then(function () {
        var moved = rowOf(id);
        // Open the folder it went into so it can be seen to have landed.
        for (var f = moved && moved.closest("details"); f; f = f.parentElement.closest("details")) f.open = true;
      });
    }).catch(function () { flash(say("network"), "error"); });
  });

  // ── The vault ─────────────────────────────────────────────────────────
  // Nothing opens until the notes key does. With no master password yet the
  // page asks for one first; with one, it asks for it unless an earlier
  // page left the key unlocked.
  var vaultData = document.getElementById("vault-data");
  var setupPanel = document.querySelector("[data-vault-setup]");
  var unlockPanel = document.querySelector("[data-vault-unlock]");
  var pane = document.querySelector("[data-note-pane]");
  var lockButton = document.querySelector("[data-vault-lock]");

  function panelStatus(panel, text, bad) {
    var el = panel.querySelector("[data-vault-status]");
    el.textContent = text;
    el.classList.toggle("is-failed", !!bad);
  }

  function opened() {
    if (setupPanel) setupPanel.hidden = true;
    if (unlockPanel) unlockPanel.hidden = true;
    if (lockButton) lockButton.hidden = false;
    if (filter) filter.disabled = false;
    return openTitles().then(function () {
      pane.hidden = false;
      if (!state || !titleEl) return;
      if (state.id === null) return startEditor(draftTitle(), "");
      return Promise.all([Vault.decrypt(state.title, "title"), Vault.decrypt(state.body, "body")])
        .then(function (both) { startEditor(both[0], both[1]); },
              function () { flash(say("note_unreadable"), "error"); });
    });
  }

  function lockUp() {
    var go = function () { Vault.lock().then(function () { window.location.reload(); }); };
    editor.flush().then(go, go);
  }

  if (vaultData && Vault && pane) {
    Vault.configure(JSON.parse(vaultData.textContent));
    if (filter) filter.disabled = true;

    if (!Vault.supported) {
      flash(say("vault_unsupported"), "error");
    } else if (!Vault.exists()) {
      setupPanel.hidden = false;
      setupPanel.querySelector("input").focus();
    } else {
      Vault.restore().then(function (ok) {
        if (ok) return opened();
        unlockPanel.hidden = false;
        unlockPanel.querySelector("input[type=password]").focus();
      });
    }

    if (setupPanel) {
      setupPanel.addEventListener("submit", function (e) {
        e.preventDefault();
        var form = e.target;
        var pw = form.elements.master.value;
        if (pw.length < 10) return panelStatus(setupPanel, say("vault_short"), true);
        if (pw !== form.elements.master_again.value) return panelStatus(setupPanel, say("vault_mismatch"), true);
        form.querySelector("button").disabled = true;
        panelStatus(setupPanel, say("vault_creating"));
        var vaultInfo = JSON.parse(vaultData.textContent);
        // Notes written before there was a vault are sealed here and swapped
        // in, together with the new key, in one go.
        fetch(vaultInfo.plain_url, { credentials: "same-origin" })
          .then(function (r) { return r.json(); })
          .then(function (plain) {
            return Vault.create(pw).then(function (made) {
              return Promise.all((plain.notes || []).map(function (n) {
                return Promise.all([made.seal(n.title, "title"), made.seal(n.body || "", "body")])
                  .then(function (s) { return { id: n.id, title: s[0], body: s[1] }; });
              })).then(function (notes) {
                var body = { salt: made.vault.salt, rounds: made.vault.rounds, key: made.vault.key, notes: notes };
                return shared.post(vaultInfo.setup_url, body).then(function (res) {
                  if (!res.ok) throw new Error(res.body.message || say("vault_failed"));
                  return made.commit();
                });
              });
            });
          })
          .then(function () { window.location.reload(); })
          .catch(function (err) {
            form.querySelector("button").disabled = false;
            panelStatus(setupPanel, (err && err.message) || say("vault_failed"), true);
          });
      });
    }

    if (unlockPanel) {
      unlockPanel.addEventListener("submit", function (e) {
        e.preventDefault();
        var form = e.target, button = form.querySelector("button");
        button.disabled = true;
        panelStatus(unlockPanel, say("vault_unlocking"));
        Vault.unlock(form.elements.master.value)
          .then(function () { form.reset(); return opened(); },
                function () {
                  panelStatus(unlockPanel, say("vault_wrong"), true);
                  form.elements.master.select();
                })
          .then(function () { button.disabled = false; });
      });
    }

    if (lockButton) lockButton.addEventListener("click", lockUp);

    // The idle lock: once the key has gone unused too long, save what is
    // owed and lock.
    setInterval(function () { if (Vault.exists() && !pane.hidden && !Vault.alive()) lockUp(); }, 15000);
    ["keydown", "pointerdown"].forEach(function (kind) {
      document.addEventListener(kind, function () { Vault.touch(); }, { passive: true });
    });
  }
})();

// The notes vault, in the browser. Everything that touches the master
// password or the notes key happens here, and none of it leaves the page:
// the server is only ever sent what this file has sealed. vault.py has the
// scheme; in short:
//
//   master password --PBKDF2-SHA256, salt, rounds--> key-encrypting key
//   key-encrypting key --AES-GCM--> seals a random 256-bit notes key
//   notes key --AES-GCM, fresh nonce--> seals each note's title and body
//
// Each sealed value carries a label (additional authenticated data), so a
// title cannot be passed off as a body or as the notes key.
//
// Once unlocked, the notes key is kept in IndexedDB as a non-extractable
// CryptoKey: pages can use it, but not even this script can read its bytes
// back out. It is dropped after IDLE_MS without use, on Lock, on signing
// out, and when the master password changes elsewhere.
(function () {
  "use strict";

  var subtle = window.crypto && window.crypto.subtle;
  var encoder = new TextEncoder();
  var decoder = new TextDecoder();
  var ROUNDS = 600000;               // OWASP's figure for PBKDF2-HMAC-SHA256
  var IDLE_MS = 30 * 60 * 1000;
  var DB_NAME = "villainy-vault", STORE = "keys", SLOT = "notes";
  var LABEL = { key: "villainy:notes-key", title: "villainy:note-title", body: "villainy:note-body" };

  // ── Encoding ──────────────────────────────────────────────────────────
  function b64(bytes) {
    var bin = "";
    bytes = new Uint8Array(bytes);
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function unb64(text) {
    var bin = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function random(n) { return window.crypto.getRandomValues(new Uint8Array(n)); }

  // ── Primitives ────────────────────────────────────────────────────────
  function stretch(password, salt, rounds) {
    return subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveKey"])
      .then(function (base) {
        return subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt: salt, iterations: rounds },
                                base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
      });
  }

  function seal(key, bytes, label) {
    var iv = random(12);
    return subtle.encrypt({ name: "AES-GCM", iv: iv, additionalData: encoder.encode(label) }, key, bytes)
      .then(function (ct) { return "v1." + b64(iv) + "." + b64(ct); });
  }

  function unseal(key, sealed, label) {
    var parts = String(sealed || "").split(".");
    if (parts.length !== 3 || parts[0] !== "v1") return Promise.reject(new Error("not sealed"));
    return subtle.decrypt({ name: "AES-GCM", iv: unb64(parts[1]), additionalData: encoder.encode(label) },
                          key, unb64(parts[2]));
  }

  function useKey(raw) {
    return subtle.importKey("raw", raw, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
  }

  // ── Where the unlocked key waits between pages ─────────────────────────
  function store(mode, work) {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) { reject(new Error("no indexedDB")); return; }
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () { req.result.createObjectStore(STORE); };
      req.onerror = function () { reject(req.error); };
      req.onsuccess = function () {
        var db = req.result;
        var tx = db.transaction(STORE, mode);
        var result = work(tx.objectStore(STORE));
        tx.oncomplete = function () { db.close(); resolve(result && result.result); };
        tx.onerror = tx.onabort = function () { db.close(); reject(tx.error); };
      };
    });
  }
  function load() { return store("readonly", function (s) { return s.get(SLOT); }).catch(function () { return null; }); }
  function save(record) { return store("readwrite", function (s) { s.put(record, SLOT); }).catch(function () {}); }
  function forget() { return store("readwrite", function (s) { s.delete(SLOT); }).catch(function () {}); }

  // ── The vault ─────────────────────────────────────────────────────────
  var config = null;   // {user, vault: {salt, rounds, key} | null}
  var key = null;      // the notes key, while unlocked
  var until = 0;
  var written = 0;

  function keep() {
    until = Date.now() + IDLE_MS;
    written = Date.now();
    return save({ user: config.user, sealed: config.vault.key, key: key, until: until });
  }

  var Vault = {
    supported: !!subtle,

    configure: function (data) { config = data; },
    exists: function () { return !!(config && config.vault); },
    alive: function () { return !!key && Date.now() < until; },

    // The key left by an earlier page, if it is still this account's, still
    // the current one, and not idle too long.
    restore: function () {
      if (!Vault.exists()) return Promise.resolve(false);
      return load().then(function (rec) {
        if (rec && rec.user === config.user && rec.sealed === config.vault.key &&
            rec.until > Date.now() && rec.key) {
          key = rec.key;
          return keep().then(function () { return true; });
        }
        if (rec) forget();
        return false;
      });
    },

    // Rejects on a wrong master password: the notes key fails to unseal.
    unlock: function (password) {
      var v = config.vault;
      return stretch(password, unb64(v.salt), v.rounds)
        .then(function (kek) { return unseal(kek, v.key, LABEL.key); })
        .then(function (raw) {
          var bytes = new Uint8Array(raw);
          return useKey(bytes).then(function (k) { bytes.fill(0); return k; });
        })
        .then(function (k) { key = k; return keep(); });
    },

    lock: function () { key = null; until = 0; return forget(); },

    // Activity pushes the idle lock back. Cheap to call on every keystroke.
    touch: function () {
      if (!key) return;
      until = Date.now() + IDLE_MS;
      if (Date.now() - written > 60000) keep();
    },

    // A brand-new vault. Resolves to what the server stores and a commit()
    // that starts using the key once the server has accepted it.
    create: function (password) {
      var salt = random(16), raw = random(32);
      return stretch(password, salt, ROUNDS)
        .then(function (kek) { return seal(kek, raw, LABEL.key); })
        .then(function (sealedKey) {
          return useKey(raw).then(function (k) {
            raw.fill(0);
            return {
              vault: { salt: b64(salt), rounds: ROUNDS, key: sealedKey },
              seal: function (text, field) { return seal(k, encoder.encode(text), LABEL[field]); },
              commit: function () {
                config.vault = { salt: b64(salt), rounds: ROUNDS, key: sealedKey };
                key = k;
                return keep();
              }
            };
          });
        });
    },

    // The same notes key under a new master password. Rejects if the old
    // one is wrong.
    rekey: function (oldPassword, newPassword) {
      var v = config.vault, salt = random(16), bytes;
      return stretch(oldPassword, unb64(v.salt), v.rounds)
        .then(function (kek) { return unseal(kek, v.key, LABEL.key); })
        .then(function (raw) {
          bytes = new Uint8Array(raw);
          return stretch(newPassword, salt, ROUNDS);
        })
        .then(function (kek) { return seal(kek, bytes, LABEL.key); })
        .then(function (sealedKey) {
          return useKey(bytes).then(function (k) {
            bytes.fill(0);
            return {
              vault: { salt: b64(salt), rounds: ROUNDS, key: sealedKey, was: v.key },
              commit: function () {
                config.vault = { salt: b64(salt), rounds: ROUNDS, key: sealedKey };
                key = k;
                return keep();
              }
            };
          });
        });
    },

    encrypt: function (text, field) {
      if (!key) return Promise.reject(new Error("locked"));
      return seal(key, encoder.encode(text), LABEL[field]);
    },
    decrypt: function (sealed, field) {
      if (!key) return Promise.reject(new Error("locked"));
      return unseal(key, sealed, LABEL[field]).then(function (bytes) { return decoder.decode(bytes); });
    },

    forget: forget
  };

  window.Vault = Vault;

  // ── Account page: a new master password ────────────────────────────────
  var shared = window.BRANCHWORK || {};
  var say = shared.say || function (k) { return k; };
  var form = document.querySelector("[data-vault-rekey]");
  var data = document.getElementById("vault-data");
  if (form && data) {
    Vault.configure(JSON.parse(data.textContent));
    var status = form.querySelector("[data-vault-status]");
    var tell = function (text, bad) { status.textContent = text; status.classList.toggle("is-failed", !!bad); };
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var old = form.elements.old_master.value, next = form.elements.new_master.value;
      if (next.length < 10) return tell(say("vault_short"), true);
      if (next !== form.elements.new_master_again.value) return tell(say("vault_mismatch"), true);
      tell(say("vault_rekeying"));
      Vault.rekey(old, next)
        .then(function (made) {
          return shared.post(form.action, made.vault).then(function (res) {
            if (!res.ok) throw new Error(res.body.message || say("vault_failed"));
            return made.commit();
          });
        }, function () { throw new Error(say("vault_wrong")); })
        .then(function () { form.reset(); tell(say("vault_rekeyed")); })
        .catch(function (err) { tell(err.message, true); });
    });
  }
})();

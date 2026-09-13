"""Build the copy editor page from villainy.toml.

    .venv\\Scripts\\python copy\\export_editor.py

Writes copy/editor.html: every line grouped by the screen it appears on, with
the comment above each key as its note. The page saves edits to its own
database; copy/apply_edits.py writes them back into the catalogue.
"""
import json
import os
import re
import tomllib
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOGUE = os.path.join(HERE, "villainy.toml")
TEMPLATE = os.path.join(HERE, "editor.template.html")
OUT = os.path.join(HERE, "editor.html")

TABLE = re.compile(r"^\[([A-Za-z0-9_.]+)\]\s*$")
KEY = re.compile(r"^([A-Za-z0-9_-]+)\s*=")


def _flat(tree, prefix=""):
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _flat(value, path + ".")
        else:
            yield path, value


def screens():
    """Screens in file order, each with its lines and their notes."""
    values = dict(_flat(tomllib.load(open(CATALOGUE, "rb"))))
    out, by_root = [], {}
    table, note = None, []
    for raw in open(CATALOGUE, encoding="utf-8"):
        line = raw.rstrip("\n")
        if m := TABLE.match(line):
            table, note = m.group(1), []
            root = table.split(".")[0]
            name = values.get(f"{table}._screen")
            if name:
                screen = {"id": table.replace(".", "-"), "name": name,
                          "about": values.get(f"{table}._about", ""), "lines": []}
                out.append(screen)
                by_root[root] = screen
            continue
        if line.startswith("#"):
            if table is not None:
                note.append(line.lstrip("# ").strip())
            continue
        if not line.strip():
            note = []
            continue
        if table and (m := KEY.match(line)) and not m.group(1).startswith("_"):
            key = f"{table}.{m.group(1)}"
            screen = by_root.get(table.split(".")[0])
            if screen is not None:
                screen["lines"].append({"key": key, "text": values[key], "note": " ".join(note)})
            note = []
    return out


def main():
    data = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "screens": screens()}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = open(TEMPLATE, encoding="utf-8").read().replace("__COPY_DATA__", blob)
    open(OUT, "w", encoding="utf-8", newline="").write(html)
    total = sum(len(s["lines"]) for s in data["screens"])
    print(f"wrote {os.path.relpath(OUT)}: {total} lines across {len(data['screens'])} screens")


if __name__ == "__main__":
    main()

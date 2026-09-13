"""Write edits from the copy editor back into villainy.toml.

    .venv\\Scripts\\python copy\\apply_edits.py <folder of edit .json files>

Each file holds one edited line, {"key": ..., "text": ...}, as the editor's
database stores them. A line is refused, and the file left untouched, if its
{placeholders} no longer match the original: the app fills those in, and a
renamed or missing one would print as a raw {brace} or break the page. The
catalogue is re-parsed before it is saved, so a bad write cannot land.
"""
import glob
import json
import os
import re
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOGUE = os.path.join(HERE, "villainy.toml")
TABLE = re.compile(r"^\[([A-Za-z0-9_.]+)\]\s*$")
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _flat(tree, prefix=""):
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _flat(value, path + ".")
        else:
            yield path, value


def main(folder: str) -> int:
    current = dict(_flat(tomllib.load(open(CATALOGUE, "rb"))))
    edits = {}
    for path in glob.glob(os.path.join(folder, "**", "*.json"), recursive=True):
        doc = json.load(open(path, encoding="utf-8"))
        if isinstance(doc, dict) and "key" in doc and "text" in doc:
            edits[doc["key"]] = doc["text"]

    applied, refused = {}, {}
    for key, text in sorted(edits.items()):
        if key not in current:
            refused[key] = "no such key any more"
        elif not text.strip():
            refused[key] = "empty"
        elif set(PLACEHOLDER.findall(text)) != set(PLACEHOLDER.findall(current[key])):
            want = ", ".join("{%s}" % p for p in sorted(set(PLACEHOLDER.findall(current[key])))) or "none"
            refused[key] = f"placeholders changed (needs exactly: {want})"
        elif text != current[key]:
            applied[key] = text

    lines = open(CATALOGUE, encoding="utf-8").read().split("\n")
    table = None
    for i, line in enumerate(lines):
        if m := TABLE.match(line):
            table = m.group(1)
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)(\s*=\s*)", line)
        if table and m and f"{table}.{m.group(1)}" in applied:
            lines[i] = m.group(1) + m.group(2) + json.dumps(applied[f"{table}.{m.group(1)}"], ensure_ascii=False)

    updated = "\n".join(lines)
    check = dict(_flat(tomllib.loads(updated)))          # refuse to save a broken file
    assert all(check[k] == v for k, v in applied.items()), "a line did not round-trip"
    open(CATALOGUE, "w", encoding="utf-8", newline="").write(updated)

    for key, text in applied.items():
        print(f"  applied  {key}: {text}")
    for key, why in refused.items():
        print(f"  REFUSED  {key}: {why}")
    print(f"{len(applied)} applied, {len(refused)} refused, "
          f"{len(edits) - len(applied) - len(refused)} unchanged")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

"""Load runbook markdown docs, strip frontmatter, expose stable doc_ids."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

RUNBOOKS_DIR = Path(__file__).resolve().parents[1] / "data" / "runbooks"
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


@dataclass
class Doc:
    doc_id: str            # stable id = filename stem, e.g. "ImagePullBackOff-registry"
    title: str
    categories: list[str]
    text: str              # body with frontmatter removed


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    m = _FRONTMATTER.match(raw)
    if not m:
        return {}, raw
    meta: dict = {}
    cats: list[str] = []
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if line.startswith("title:"):
            meta["title"] = line.split(":", 1)[1].strip()
        elif line.strip().startswith("- "):
            cats.append(line.strip()[2:].strip())
    meta["categories"] = cats
    return meta, raw[m.end():]


def load_corpus(runbooks_dir: Path = RUNBOOKS_DIR) -> list[Doc]:
    docs: list[Doc] = []
    for path in sorted(runbooks_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        docs.append(Doc(
            doc_id=path.stem,
            title=meta.get("title", path.stem),
            categories=meta.get("categories", []),
            text=body.strip(),
        ))
    if not docs:
        raise FileNotFoundError(f"No .md runbooks found in {runbooks_dir}")
    return docs


if __name__ == "__main__":
    docs = load_corpus()
    print(f"{len(docs)} docs")
    d = docs[0]
    print(f"sample doc_id={d.doc_id!r} title={d.title!r} cats={d.categories} chars={len(d.text)}")
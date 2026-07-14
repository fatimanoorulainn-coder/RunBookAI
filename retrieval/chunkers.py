"""Three chunking strategies, each returning stable-id Chunk objects.

fixed_size    : 500 chars / 50 overlap, ignores structure (Day 12 baseline).
heading_aware : split on ##/### headings, each chunk prefixed with its heading path.
parent_child  : small child chunk for matching; full parent section returned as context.

Chunk.text  is what gets embedded / matched.
Chunk.context is what the agent should actually read (== text except for parent_child).
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from retrieval.corpus import Doc, load_corpus

HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)


@dataclass
class Chunk:
    chunk_id: str      # stable, e.g. "ImagePullBackOff-registry::fixed::0003"
    doc_id: str
    text: str          # embedded + matched
    context: str       # returned to the agent (may be larger than text)
    heading: str = ""


def fixed_size(docs: list[Doc], size: int = 500, overlap: int = 50) -> list[Chunk]:
    out: list[Chunk] = []
    for d in docs:
        t, i, n = d.text, 0, 0
        step = max(1, size - overlap)
        while i < len(t):
            piece = t[i:i + size]
            if piece.strip():
                out.append(Chunk(f"{d.doc_id}::fixed::{n:04d}", d.doc_id, piece, piece))
                n += 1
            i += step
    return out


def _sections(text: str) -> list[tuple[str, str]]:
    """Split into (heading_path, body) on ## / ### boundaries."""
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [("", text)]
    sections, h1 = [], ""
    # preamble before first heading
    if matches[0].start() > 0:
        pre = text[:matches[0].start()].strip()
        if pre:
            sections.append(("", pre))
    for idx, m in enumerate(matches):
        level, title = len(m.group(1)), m.group(2).strip()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        if level <= 2:
            h1 = title
            path = title
        else:
            path = f"{h1} > {title}" if h1 else title
        if body:
            sections.append((path, body))
    return sections


def heading_aware(docs: list[Doc]) -> list[Chunk]:
    out: list[Chunk] = []
    for d in docs:
        for n, (path, body) in enumerate(_sections(d.text)):
            prefixed = f"[{path}] {body}" if path else body
            out.append(Chunk(f"{d.doc_id}::heading::{n:04d}", d.doc_id, prefixed, prefixed, path))
    return out


def parent_child(docs: list[Doc], child_size: int = 300, overlap: int = 40) -> list[Chunk]:
    """Match on small children; return the whole parent section as context."""
    out: list[Chunk] = []
    for d in docs:
        for s, (path, parent) in enumerate(_sections(d.text)):
            step = max(1, child_size - overlap)
            i, c = 0, 0
            while i < len(parent):
                child = parent[i:i + child_size]
                if child.strip():
                    ctx = f"[{path}]\n{parent}" if path else parent
                    out.append(Chunk(f"{d.doc_id}::pc::{s:04d}-{c:04d}", d.doc_id, child, ctx, path))
                    c += 1
                i += step
    return out


CHUNKERS = {"fixed": fixed_size, "heading": heading_aware, "parent_child": parent_child}

if __name__ == "__main__":
    docs = load_corpus()
    for name, fn in CHUNKERS.items():
        chunks = fn(docs)
        avg = sum(len(c.text) for c in chunks) / len(chunks)
        print(f"{name:13s} {len(chunks):4d} chunks  avg_text={avg:6.0f}  e.g. {chunks[10].chunk_id}")
#!/usr/bin/env python3
"""Create a flat NotebookLM upload bundle from techstack/research.

Purpose
- Given a query, select the most relevant research docs using:
  - keyword hit count (case-insensitive)
  - recency (mtime)
- Copy the top matches into a flat output directory for easy drag/drop.

This is intentionally dependency-free (stdlib only).

Examples
  # Top 25 matches from last 180 days
  ./scripts/research_bundle.py --query "irsa s3" --days 180 --limit 25

  # Bundle everything touched in last 14 days (no query)
  ./scripts/research_bundle.py --days 14 --limit 200

Output
- <out>/index.md       : quick human-readable index
- <out>/manifest.json  : machine-readable list
- <out>/*.md           : flattened copies of selected docs
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Candidate:
    path: Path
    mtime: float
    age_days: float
    hits: int
    score: float
    out_name: str


def _now_ts() -> float:
    return dt.datetime.now(dt.timezone.utc).timestamp()


def _tokenize_query(q: str) -> list[str]:
    # Split on whitespace, keep simple; user can pass regex via --regex.
    return [t.strip() for t in q.split() if t.strip()]


def _safe_flat_name(rel: Path) -> str:
    # Flatten by replacing separators with '__' and keeping extension.
    # Example: research/foo/bar.md -> research__foo__bar.md
    s = str(rel).replace(os.sep, "__")
    s = s.replace(" ", "_")
    # Guard against very long names
    if len(s) > 180:
        h = hashlib.sha1(str(rel).encode("utf-8")).hexdigest()[:10]
        stem = Path(s).stem[:80]
        suf = Path(s).suffix
        s = f"{stem}__{h}{suf}"
    return s


def _count_hits(path: Path, patterns: list[re.Pattern]) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0
    hits = 0
    for pat in patterns:
        hits += len(pat.findall(text))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="", help="Search terms (space-separated).")
    ap.add_argument("--regex", action="store_true", help="Treat --query as a single regex pattern.")
    ap.add_argument("--days", type=int, default=365, help="Only include files modified within N days (default: 365).")
    ap.add_argument("--limit", type=int, default=50, help="Max number of files to include (default: 50).")
    ap.add_argument("--research-dir", default="research", help="Research directory relative to repo root (default: research).")
    ap.add_argument("--out", default="notebook-bundles", help="Output root dir (default: notebook-bundles).")
    ap.add_argument("--name", default="", help="Optional bundle name. Default: timestamp + query slug.")
    ap.add_argument("--ext", default="md,mdx", help="Comma-separated extensions to include (default: md,mdx).")

    args = ap.parse_args()

    repo_root = Path.cwd()
    research_dir = (repo_root / args.research_dir).resolve()
    if not research_dir.exists() or not research_dir.is_dir():
        print(f"ERROR: research dir not found: {research_dir}", file=sys.stderr)
        return 2

    exts = {"." + e.strip().lstrip(".") for e in args.ext.split(",") if e.strip()}

    now = _now_ts()
    cutoff = now - (args.days * 86400)

    # Build patterns
    patterns: list[re.Pattern] = []
    if args.query:
        if args.regex:
            patterns = [re.compile(args.query, re.IGNORECASE)]
        else:
            toks = _tokenize_query(args.query)
            patterns = [re.compile(re.escape(t), re.IGNORECASE) for t in toks]

    # Collect candidates
    candidates: list[Candidate] = []
    for p in sorted(research_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        st = p.stat()
        if st.st_mtime < cutoff:
            continue
        age_days = max(0.0, (now - st.st_mtime) / 86400.0)

        hits = _count_hits(p, patterns) if patterns else 0

        # Score: prioritize keyword matches heavily, then recency.
        # Recency component: 1.0 for today, ~0.0 near cutoff.
        recency = max(0.0, 1.0 - (age_days / max(1, args.days)))
        score = (hits * 100.0) + (recency * 10.0)

        rel = p.relative_to(repo_root)
        out_name = _safe_flat_name(rel)

        candidates.append(Candidate(path=p, mtime=st.st_mtime, age_days=age_days, hits=hits, score=score, out_name=out_name))

    # If query provided, drop zero-hit docs unless user explicitly wants only recency.
    if patterns:
        candidates = [c for c in candidates if c.hits > 0]

    candidates.sort(key=lambda c: (c.score, c.mtime), reverse=True)
    selected = candidates[: max(0, args.limit)]

    # Output directory
    out_root = (repo_root / args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = "bundle"
    if args.name:
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", args.name).strip("-") or "bundle"
    elif args.query:
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", args.query.lower()).strip("-")[:60] or "bundle"

    bundle_dir = out_root / f"{ts}__{slug}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    for c in selected:
        shutil.copy2(c.path, bundle_dir / c.out_name)

    # Write manifest
    manifest = {
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "query": args.query,
        "regex": bool(args.regex),
        "days": args.days,
        "limit": args.limit,
        "researchDir": str(Path(args.research_dir)),
        "selected": [
            {
                "source": str(c.path),
                "relative": str(c.path.relative_to(repo_root)),
                "out": c.out_name,
                "mtime": dt.datetime.fromtimestamp(c.mtime, tz=dt.timezone.utc).isoformat(),
                "ageDays": round(c.age_days, 2),
                "hits": c.hits,
                "score": round(c.score, 3),
            }
            for c in selected
        ],
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Write index
    lines = []
    lines.append(f"# NotebookLM bundle: {slug}\n")
    lines.append(f"- Created: {manifest['createdAt']}\n")
    lines.append(f"- Query: `{args.query or '(none)'}`\n")
    lines.append(f"- Window: last {args.days} days\n")
    lines.append(f"- Files: {len(selected)}\n")
    lines.append("\n## Files\n")
    for i, c in enumerate(selected, 1):
        rel = c.path.relative_to(repo_root)
        lines.append(f"{i}. `{c.out_name}` ← `{rel}` (hits={c.hits}, ageDays={c.age_days:.1f})")
    (bundle_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(bundle_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

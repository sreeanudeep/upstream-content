#!/usr/bin/env python3
"""Validate every pack, then rebuild manifest.json and index/titles.txt. Standard library only.

    python tools/build.py               validate, then rebuild (writes nothing if any pack is invalid)
    python tools/build.py --self-check  run the built-in checks
"""
import copy
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

TOPICS = {"mind", "world", "life", "survival"}
KINDS = {"book", "paper", "article", "organization", "wikipedia", "talk"}
LIMITS = {"title": (10, 80), "body": (150, 600), "deeper": (400, 1400)}
IDEA_KEYS = {"id", "topic", "tags", "title", "body", "deeper", "source"}
SOURCE_KEYS = {"kind", "title", "author", "url"}
TAG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PACK_ID = re.compile(r"^\d{4}-w\d{2}(-[a-z])?$")
JOURNEY_ID = re.compile(r"^j-\d{4}-w\d{2}-[a-z0-9]+(-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def norm(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def check_idea(idea, pack_id, n, errors):
    where = f"{pack_id} #{n}"
    if not isinstance(idea, dict):
        errors.append(f"{where}: not an object")
        return
    if set(idea) != IDEA_KEYS:
        errors.append(f"{where}: keys must be exactly {sorted(IDEA_KEYS)}")
    if idea.get("id") != f"{pack_id}-{n:03d}":
        errors.append(f"{where}: id must be {pack_id}-{n:03d}")
    if idea.get("topic") not in TOPICS:
        errors.append(f"{where}: topic must be one of {sorted(TOPICS)}")
    tags = idea.get("tags")
    if not (isinstance(tags, list) and 1 <= len(tags) <= 4 and all(isinstance(t, str) and TAG.match(t) for t in tags)):
        errors.append(f"{where}: tags must be 1-4 lowercase-hyphenated words")
    for field, (lo, hi) in LIMITS.items():
        value = idea.get(field)
        if not isinstance(value, str) or not lo <= len(value) <= hi:
            errors.append(f"{where}: {field} must be {lo}-{hi} characters")
        elif any(c in value for c in "!—–"):
            errors.append(f"{where}: no exclamation marks or long dashes in {field}")
    deeper = idea.get("deeper")
    if isinstance(deeper, str) and len([p for p in deeper.split("\n\n") if p.strip()]) != 3:
        errors.append(f"{where}: deeper must be three paragraphs separated by a blank line")
    src = idea.get("source")
    if not isinstance(src, dict) or not set(src) <= SOURCE_KEYS:
        errors.append(f"{where}: source must be an object with keys from {sorted(SOURCE_KEYS)}")
        return
    if src.get("kind") not in KINDS:
        errors.append(f"{where}: source.kind must be one of {sorted(KINDS)}")
    if not isinstance(src.get("title"), str) or not src["title"].strip():
        errors.append(f"{where}: source.title is required")
    if "author" in src and (not isinstance(src["author"], str) or not src["author"].strip()):
        errors.append(f"{where}: source.author must be a non-empty string when present")
    if "url" in src and (not isinstance(src["url"], str) or not src["url"].startswith("https://")):
        errors.append(f"{where}: source.url must start with https://")


def build(root, write=True):
    """Return a list of errors; when there are none and write is set, rebuild the manifest and the index."""
    root = Path(root)
    errors, entries, index, seen_titles = [], [], [], {}
    for path in sorted((root / "packs").glob("*.json")):
        raw = path.read_bytes()
        try:
            pack = json.loads(raw)
        except ValueError as e:
            errors.append(f"{path.name}: invalid JSON ({e})")
            continue
        pack_id = pack.get("id") if isinstance(pack, dict) else None
        if not isinstance(pack_id, str) or not PACK_ID.match(pack_id) or path.name != f"{pack_id}.json":
            errors.append(f"{path.name}: id must be YYYY-wWW[-x] and match the file name")
            continue
        if not isinstance(pack.get("publishedAt"), str) or not DATE.match(pack["publishedAt"]):
            errors.append(f"{pack_id}: publishedAt must be YYYY-MM-DD")
        ideas = pack.get("ideas")
        if not isinstance(ideas, list) or not 1 <= len(ideas) <= 400:
            errors.append(f"{pack_id}: ideas must be a list of 1-400")
            continue
        for n, idea in enumerate(ideas, 1):
            check_idea(idea, pack_id, n, errors)
            if isinstance(idea, dict) and isinstance(idea.get("title"), str):
                key = norm(idea["title"])
                if key in seen_titles:
                    errors.append(f"{pack_id} #{n}: duplicate title (also {seen_titles[key]})")
                seen_titles[key] = f"{pack_id} #{n}"
                src = idea.get("source") if isinstance(idea.get("source"), dict) else {}
                by = f"{src.get('title', '')} ({src['author']})" if src.get("author") else src.get("title", "")
                index.append(f"{idea.get('topic')} | {idea['title']} | {by} | {','.join(idea.get('tags') or [])}")
        entries.append({
            "id": pack_id, "path": f"packs/{path.name}", "count": len(ideas), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "publishedAt": pack.get("publishedAt"),
        })
    journeys, journey_index = [], []
    for path in sorted((root / "journeys").glob("*.json")):
        raw = path.read_bytes()
        try:
            j = json.loads(raw)
        except ValueError as e:
            errors.append(f"{path.name}: invalid JSON ({e})")
            continue
        jid = j.get("id") if isinstance(j, dict) else None
        if not isinstance(jid, str) or not JOURNEY_ID.match(jid) or path.name != f"{jid}.json":
            errors.append(f"{path.name}: id must be j-YYYY-wWW-slug and match the file name")
            continue
        if not isinstance(j.get("title"), str) or not 10 <= len(j["title"]) <= 60:
            errors.append(f"{jid}: title must be 10-60 characters")
        if not isinstance(j.get("summary"), str) or not 40 <= len(j["summary"]) <= 240:
            errors.append(f"{jid}: summary must be 40-240 characters")
        if j.get("topic") not in TOPICS:
            errors.append(f"{jid}: topic must be one of {sorted(TOPICS)}")
        if not isinstance(j.get("publishedAt"), str) or not DATE.match(j["publishedAt"]):
            errors.append(f"{jid}: publishedAt must be YYYY-MM-DD")
        steps = j.get("steps")
        if not isinstance(steps, list) or not 5 <= len(steps) <= 7:
            errors.append(f"{jid}: steps must be a list of 5-7 ideas")
            continue
        for n, step in enumerate(steps, 1):
            check_idea(step, jid, n, errors)
            if isinstance(step, dict) and step.get("topic") != j.get("topic"):
                errors.append(f"{jid} #{n}: step topic must match the journey topic")
            if isinstance(step, dict) and isinstance(step.get("title"), str):
                key = norm(step["title"])
                if key in seen_titles:
                    errors.append(f"{jid} #{n}: duplicate title (also {seen_titles[key]})")
                seen_titles[key] = f"{jid} #{n}"
        journey_index.append(f"{j.get('topic')} | {j.get('title')} | {j.get('summary')}")
        journeys.append({
            "id": jid, "path": f"journeys/{path.name}", "title": j.get("title"), "steps": len(steps), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "publishedAt": j.get("publishedAt"),
        })
    if errors or not write:
        return errors
    entries.sort(key=lambda e: (e["publishedAt"], e["id"]))
    journeys.sort(key=lambda e: (e["publishedAt"], e["id"]))
    manifest = {"schema": 1, "packs": entries, "journeys": journeys}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    (root / "index").mkdir(exist_ok=True)
    (root / "index" / "titles.txt").write_text("\n".join(index) + "\n", encoding="utf-8", newline="\n")
    (root / "index" / "journeys.txt").write_text("\n".join(journey_index) + "\n", encoding="utf-8", newline="\n")
    return []


def self_check():
    deeper = "Why. " + "w" * 150 + "\n\nExample. " + "e" * 150 + "\n\nApply it today. " + "a" * 150
    good = {"id": "2026-w01-001", "topic": "mind", "tags": ["decision-making"], "title": "Plan the failure first",
            "body": "b" * 200, "deeper": deeper, "source": {"kind": "book", "title": "Sources of Power", "author": "Gary Klein"}}

    def run(*ideas, pack_id="2026-w01", extra=None):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "packs").mkdir()
            for pid, items in [(pack_id, ideas)] + (extra or []):
                body = {"id": pid, "publishedAt": "2026-01-01", "ideas": list(items)}
                (Path(d) / "packs" / f"{pid}.json").write_text(json.dumps(body), encoding="utf-8", newline="\n")
            errs = build(d)
            manifest = json.loads((Path(d) / "manifest.json").read_text()) if not errs else None
            raw = (Path(d) / "packs" / f"{pack_id}.json").read_bytes()
            return errs, manifest, raw

    def bad(**change):
        idea = copy.deepcopy(good)
        idea.update(change)
        return idea

    errs, manifest, raw = run(good)
    assert errs == [], errs
    assert manifest["packs"][0]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["packs"][0]["count"] == 1
    for idea, needle in [
        (bad(topic="sport"), "topic"),
        (bad(body="too short"), "body"),
        (bad(title="Wow, look at this!"), "exclamation"),
        (bad(title="Plans fail — plan for it"), "long dashes"),
        (bad(id="2026-w01-002"), "id must be"),
        (bad(deeper="one paragraph " * 40), "three paragraphs"),
        (bad(tags=["Bad Tag"]), "tags"),
        (bad(source={"kind": "book", "title": "X", "url": "http://x.org"}), "https"),
        (bad(source={"kind": "blog", "title": "X"}), "source.kind"),
        (bad(extra="field"), "keys"),
    ]:
        errs, _, _ = run(idea)
        assert any(needle in e for e in errs), (needle, errs)
    dup = bad(id="2026-w02-001", title="Plan the FAILURE first.")
    errs, _, _ = run(good, extra=[("2026-w02", [dup])])
    assert any("duplicate title" in e for e in errs), errs
    def journey(jid, n, topic="mind"):
        steps = []
        for k in range(1, n + 1):
            st = copy.deepcopy(good)
            st.update(id=f"{jid}-{k:03d}", title=f"Journey step number {k}", topic=topic)
            steps.append(st)
        return {"id": jid, "title": "Think like a Stoic", "summary": "Six short steps from the Enchiridion to a calmer week.",
                "topic": "mind", "publishedAt": "2026-01-01", "steps": steps}

    def run_journey(j):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "packs").mkdir()
            (Path(d) / "journeys").mkdir()
            (Path(d) / "journeys" / f"{j['id']}.json").write_text(json.dumps(j), encoding="utf-8", newline="\n")
            errs = build(d)
            manifest = json.loads((Path(d) / "manifest.json").read_text()) if not errs else None
            return errs, manifest

    errs, manifest = run_journey(journey("j-2026-w01-stoic", 6))
    assert errs == [], errs
    assert manifest["journeys"][0]["steps"] == 6 and manifest["packs"] == []
    errs, _ = run_journey(journey("j-2026-w01-stoic", 4))
    assert any("5-7" in e for e in errs), errs
    errs, _ = run_journey(journey("j-2026-w01-stoic", 6, topic="life"))
    assert any("journey topic" in e for e in errs), errs
    print("self-check passed")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        self_check()
        sys.exit(0)
    problems = build(Path(__file__).resolve().parent.parent)
    for p in problems:
        print(p)
    if problems:
        print(f"{len(problems)} problem(s); nothing written.")
        sys.exit(1)
    print("manifest.json and index/titles.txt rebuilt.")

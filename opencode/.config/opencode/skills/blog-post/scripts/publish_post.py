#!/usr/bin/env python3
"""Add a post to a blog repo and push it (the blog-post skill's mechanics).

Picks the next post id, writes src/content/posts/<id>_<slug>.md with
frontmatter, adds the id to the subject in subjects.json, copies the hero
image to public/static/post-<slug>.jpg, then commits and pushes those files
only. Refuses to touch a repo with uncommitted changes.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BLOGS = Path(os.environ.get("BLOG_REPOS") or Path.home() / "Dropbox/Development/Personal/websites/blogs")
MAX_TAGS = {"catdevtech.net": 5}
CRITIC = re.compile(r"\{(\+\+|--|~~|>>|==)")


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check,
                          capture_output=True, text=True)


def fail(msg):
    print(f"publish_post: {msg}", file=sys.stderr)
    sys.exit(1)


def format_subjects(subjects, original):
    """4-space JSON with short lists kept on one line, as the repos have it."""
    out = json.dumps(subjects, indent=4, ensure_ascii=False)
    out = re.sub(r"\[\s*([^\[\]{}]*?)\s*\]",
                 lambda m: "[" + ", ".join(x.strip() for x in m.group(1).split(",") if x.strip()) + "]",
                 out)
    return out + ("\n" if original.endswith("\n") else "")


def clean_body(text):
    text = text.lstrip("﻿")
    if text.startswith("---\n"):  # drop any frontmatter the draft carried
        end = text.find("\n---", 4)
        if end != -1:
            text = text[end + 4:]
    lines = text.strip("\n").split("\n")
    title = ""
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]
    return "\n".join(lines).strip() + "\n", title


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", required=True)
    ap.add_argument("--body", required=True, help="markdown file with the final text")
    ap.add_argument("--title", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--subject", required=True, type=int)
    ap.add_argument("--tags", required=True, help="comma-separated")
    ap.add_argument("--image", required=True, help="hero image (JPEG)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(argv)

    repo = BLOGS / a.site
    posts = repo / "src/content/posts"
    subjects_file = repo / "subjects.json"
    if not posts.is_dir() or not subjects_file.is_file():
        fail(f"{repo} is not a blog repo (no src/content/posts or subjects.json)")

    slug = re.sub(r"[^A-Za-z0-9_]+", "_", a.slug.strip()).strip("_")
    if not slug:
        fail("empty slug")
    tags = [t.strip().lower().replace(" ", "-") for t in a.tags.split(",") if t.strip()]
    if not tags:
        fail("no tags")
    tags = tags[:MAX_TAGS.get(a.site, 6)]

    body, _ = clean_body(Path(a.body).read_text(encoding="utf-8"))
    if CRITIC.search(body):
        fail("the body still contains CriticMarkup ({++ {-- {~~ {>> {==); use the accepted final")
    image = Path(a.image)
    if not image.is_file():
        fail(f"image not found: {image}")

    subjects = json.loads(subjects_file.read_text(encoding="utf-8"))
    if str(a.subject) not in subjects:
        names = ", ".join(f"{k}={v.get('name')}" for k, v in subjects.items())
        fail(f"subject {a.subject} not in subjects.json ({names})")

    # Safety: Dropbox conflict copies inside .git break fetch with cryptic errors.
    junk = [str(p.relative_to(repo)) for p in (repo / ".git").rglob("*conflicted copy*")]
    if junk:
        fail("Dropbox conflict copies inside .git; move them out first:\n  " + "\n  ".join(junk))
    # Safety: start from a clean, current main.
    status = git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if status:
        fail(f"{a.site} has uncommitted changes; commit or stash them first:\n{status}")
    if git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
        fail(f"{a.site} is not on main")
    if not a.dry_run:
        r = git(repo, "pull", "-q", "--ff-only", "origin", "main", check=False)
        if r.returncode:
            fail(f"git pull failed: {r.stderr.strip()}")
        subjects = json.loads(subjects_file.read_text(encoding="utf-8"))

    # Idempotent: a retried publish must not post the same article twice.
    for p in posts.glob("*.md"):
        head = p.read_text(encoding="utf-8").split("\n---", 1)[0]
        m = re.search(r"^title:\s*(.+)$", head, re.M)
        if m and m.group(1).strip().strip("'\"") == a.title.strip() and "conflicted copy" not in p.name:
            pid = p.name.split("_", 1)[0]
            print(f"already published: {p.relative_to(repo)}\nurl:     https://{a.site}/post/{pid}/")
            return 0

    ids = [int(m.group(1)) for p in posts.glob("*.md")
           if "conflicted copy" not in p.name and (m := re.match(r"(\d+)_", p.name))]
    post_id = max(ids, default=0) + 1
    post_file = posts / f"{post_id}_{slug}.md"
    image_rel = f"/static/post-{slug.lower().replace('_', '-')}.jpg"
    image_dest = repo / "public" / image_rel.lstrip("/")
    if image_dest.exists():
        fail(f"{image_dest} already exists; choose another slug")

    front = (
        "---\n"
        f"title: {json.dumps(a.title.strip(), ensure_ascii=False)}\n"
        f"subject_id: {a.subject}\n"
        f"created_at: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"image: {image_rel}\n"
        f"tags: {json.dumps(tags)}\n"
        "---\n\n"
    )
    url = f"https://{a.site}/post/{post_id}/"
    print(f"post:    {post_file.relative_to(repo)}\nimage:   public{image_rel}\n"
          f"subject: {a.subject} ({subjects[str(a.subject)].get('name')})\n"
          f"tags:    {', '.join(tags)}\nurl:     {url}")
    if a.dry_run:
        print("(dry run: nothing written)")
        return 0

    post_file.write_text(front + body, encoding="utf-8")
    shutil.copyfile(image, image_dest)
    entry = subjects[str(a.subject)]
    entry.setdefault("posts", [])
    if post_id not in entry["posts"]:
        entry["posts"].append(post_id)
    subjects_file.write_text(format_subjects(subjects, subjects_file.read_text(encoding="utf-8")),
                             encoding="utf-8")

    files = [str(post_file.relative_to(repo)), str(image_dest.relative_to(repo)), "subjects.json"]
    git(repo, "add", "--", *files)
    git(repo, "commit", "-q", "-m", f"Post: {a.title.strip()}", "--", *files)
    if a.no_push:
        print("committed (not pushed)")
        return 0
    r = git(repo, "push", "-q", "origin", "main", check=False)
    if r.returncode:
        fail(f"committed locally but push failed: {r.stderr.strip()}")
    print(f"pushed; live in about 5 minutes at {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

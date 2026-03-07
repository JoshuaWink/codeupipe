"""MkDocs hook — copy every .md source as .txt in the built site.

This makes the docs curl-friendly: ``curl .../concepts.txt`` returns the
raw Markdown instead of the HTML wrapper.  A ``curl.txt`` sitemap and an
``agents.txt`` navigation guide are also generated automatically.
"""

import shutil
from pathlib import Path


_SITE_URL = "https://codeuchain.github.io/codeupipe"

_AGENT_BANNER = """\
# ── codeupipe docs ──────────────────────────────────────────────────────────
# Agent navigation guide : {site_url}/agents.txt
# All pages as plain text: {site_url}/curl.txt
# ────────────────────────────────────────────────────────────────────────────

""".format(site_url=_SITE_URL)


def on_post_build(config, **kwargs):
    docs_dir = Path(config["docs_dir"])
    site_dir = Path(config["site_dir"])

    pages = []

    for md_file in sorted(docs_dir.rglob("*.md")):
        rel = md_file.relative_to(docs_dir)
        txt_dest = site_dir / rel.with_suffix(".txt")
        txt_dest.parent.mkdir(parents=True, exist_ok=True)
        original = md_file.read_text(encoding="utf-8")
        txt_dest.write_text(_AGENT_BANNER + original, encoding="utf-8")
        pages.append(str(rel.with_suffix(".txt")))

    # Copy agents.txt verbatim (already well-formed, no banner needed)
    agents_src = docs_dir / "agents.txt"
    if agents_src.exists():
        shutil.copy2(agents_src, site_dir / "agents.txt")

    # Generate curl sitemap
    lines = [
        "codeupipe documentation (curl-friendly)",
        "=" * 43,
        "",
        "Agent navigation guide:",
        f"  curl {_SITE_URL}/agents.txt",
        "",
        "Usage:",
        f"  curl {_SITE_URL}/curl.txt              # this sitemap",
        f"  curl {_SITE_URL}/getting-started.txt   # quick start",
        f"  curl {_SITE_URL}/concepts.txt          # full API reference",
        "",
        "Available pages:",
        "",
    ]
    for page in pages:
        lines.append(f"  curl {_SITE_URL}/{page}")

    lines.append("")
    lines.append("Browse with a browser: " + _SITE_URL)
    lines.append("")

    (site_dir / "curl.txt").write_text("\n".join(lines))

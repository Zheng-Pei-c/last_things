from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path


ROOT = Path("/Users/zheng/Dropbox/notes/last_things")
BODY_DIR = ROOT / "body"
HTML_DIR = ROOT / "html"
HTML_BODY_DIR = HTML_DIR / "body"

TITLE = "An Amateur's Guide to Last Things, Ever After"
SUBTITLE = "One Thousand and One Deaths"


def slug_to_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def rewrite_link(match: re.Match[str]) -> str:
    label = match.group(1)
    target = match.group(2)
    if target.endswith(".md"):
        if target == "README.md":
            target = "readme.html"
        elif target == "LICENSE.md":
            target = "license.html"
        elif target == "main.md":
            target = "index.html"
        else:
            target = target[:-3] + ".html"
    return f'<a href="{html.escape(target, quote=True)}">{label}</a>'


def inline_format(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", rewrite_link, text)
    return text


def md_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    in_ul = False
    in_ol = False
    in_blockquote = False
    in_code = False
    in_table = False
    in_poem = False
    linebreak_token = "%%LAST_THINGS_BR%%"

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            joined = " ".join(paragraph).strip()
            formatted = inline_format(joined).replace(linebreak_token, "<br>")
            out.append(f"<p>{formatted}</p>")
            paragraph = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def close_blockquote() -> None:
        nonlocal in_blockquote
        if in_blockquote:
            flush_paragraph()
            out.append("</blockquote>")
            in_blockquote = False

    def close_poem() -> None:
        nonlocal in_poem
        if in_poem:
            flush_paragraph()
            out.append("</div>")
            in_poem = False

    for line in lines:
        stripped = line.strip()

        if line.startswith("```"):
            flush_paragraph()
            close_lists()
            close_blockquote()
            close_poem()
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            out.append(html.escape(line))
            continue

        if "|" in line and stripped and not stripped.startswith("#"):
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 3:
                if not in_table:
                    flush_paragraph()
                    close_lists()
                    close_blockquote()
                    out.append("<table>")
                    in_table = True
                if re.fullmatch(r"\|?[\s:-]+\|[\s|:-]*", line):
                    continue
                cells = [p for p in parts if p != ""]
                tag = "th" if not any("<td>" in row for row in out[-1:]) else "td"
                row_html = "".join(f"<{tag}>{inline_format(cell)}</{tag}>" for cell in cells)
                out.append(f"<tr>{row_html}</tr>")
                continue
        elif in_table:
            out.append("</table>")
            in_table = False

        if not stripped:
            flush_paragraph()
            close_lists()
            close_blockquote()
            if in_poem:
                continue
            continue

        if stripped == "---":
            flush_paragraph()
            close_lists()
            close_blockquote()
            close_poem()
            out.append("<hr>")
            continue

        if stripped == "::: poem":
            flush_paragraph()
            close_lists()
            close_blockquote()
            close_poem()
            out.append('<div class="poem">')
            in_poem = True
            continue

        if stripped == ":::" and in_poem:
            close_poem()
            continue

        if stripped.startswith("> "):
            flush_paragraph()
            close_lists()
            close_poem()
            if not in_blockquote:
                out.append("<blockquote>")
                in_blockquote = True
            out.append(f"<p>{inline_format(stripped[2:])}</p>")
            continue
        elif in_blockquote:
            close_blockquote()

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            flush_paragraph()
            close_lists()
            close_poem()
            level = len(heading_match.group(1))
            out.append(f"<h{level}>{inline_format(heading_match.group(2).strip())}</h{level}>")
            continue

        ul_match = re.match(r"^-\s+(.*)$", stripped)
        if ul_match:
            flush_paragraph()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline_format(ul_match.group(1))}</li>")
            continue

        ol_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ol_match:
            flush_paragraph()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline_format(ol_match.group(1))}</li>")
            continue

        if line.endswith("  "):
            paragraph.append(line.rstrip() + linebreak_token)
        else:
            paragraph.append(line)

    flush_paragraph()
    close_lists()
    close_blockquote()
    close_poem()
    if in_table:
        out.append("</table>")
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def page_template(
    title: str,
    content: str,
    *,
    nested: bool = False,
    body_attrs: str = "",
    script: str = "",
) -> str:
    stylesheet = "../style.css" if nested else "style.css"
    home_link = "../index.html" if nested else "index.html"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} | {html.escape(TITLE)}</title>
  <link rel="stylesheet" href="{stylesheet}">
</head>
<body {body_attrs}>
  <header class="site-header">
    <a class="home-link" href="{home_link}">{html.escape(TITLE)}</a>
    <div class="subtitle">{html.escape(SUBTITLE)}</div>
  </header>
  <main class="page">
    {content}
  </main>
  {script}
</body>
</html>
"""


STYLE = """
:root {
  --paper: #f8f4eb;
  --ink: #1f1a17;
  --muted: #6f655d;
  --line: #d7cec3;
  --accent: #9d3d18;
  --accent-soft: rgba(157, 61, 24, 0.08);
  --panel: rgba(255, 252, 247, 0.92);
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Georgia, "Times New Roman", serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top, rgba(157, 61, 24, 0.10), transparent 30%),
    linear-gradient(180deg, #efe6d6 0%, var(--paper) 20%, #f4efe6 100%);
  line-height: 1.65;
}

.site-header, .page {
  width: min(860px, calc(100% - 2rem));
  margin: 0 auto;
}

.site-header {
  padding: 2rem 0 1rem;
  position: relative;
}

.home-link {
  color: var(--accent);
  text-decoration: none;
  font-size: clamp(1.6rem, 4vw, 2.4rem);
}

.subtitle {
  color: var(--muted);
  margin-top: 0.2rem;
  font-style: italic;
}

.page {
  padding-bottom: 4rem;
}

.content,
.toc-shell,
.story-nav,
.control-shell {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(69, 47, 30, 0.08);
}

.content {
  padding: 2rem;
}

.content img {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 1.2rem auto;
  border-radius: 18px;
  border: 1px solid var(--line);
  box-shadow: 0 16px 36px rgba(69, 47, 30, 0.10);
  background: rgba(255, 255, 255, 0.7);
}

.poem {
  text-align: center;
}

.poem p {
  margin-left: auto;
  margin-right: auto;
  max-width: 32rem;
}

.book-front {
  padding: 1.4rem 0 0.6rem;
}

.eyebrow {
  margin: 0 0 0.4rem;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.76rem;
}

.front-subtitle,
.front-note,
.toc-meta,
.toc-id,
.featured-meta p,
.reading-mode-note,
.story-id,
.copyright-note {
  color: var(--muted);
}

.copyright-note {
  border-top: 1px solid #000;
  margin-top: 1.6rem;
  padding-top: 0.8rem;
}

.control-shell {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  align-items: center;
  column-gap: 0.7rem;
  row-gap: 0.5rem;
  padding: 0.9rem 1rem;
  margin: 1rem 0 0.9rem;
}

.mode-label {
  margin-right: 0.2rem;
  font-size: 0.95rem;
}

.reader-tools {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.tool-label {
  color: var(--muted);
  font-size: 0.9rem;
}

.tool-value {
  min-width: 2.6rem;
  text-align: center;
  border: 1px solid rgba(157, 61, 24, 0.22);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  background: white;
  color: var(--ink);
}

.tool-button {
  appearance: none;
  border: 1px solid rgba(157, 61, 24, 0.22);
  background: white;
  border-radius: 999px;
  padding: 0.2rem 0.65rem;
  cursor: pointer;
  font: inherit;
  color: var(--ink);
}

.mode-toggle {
  appearance: none;
  border: 1px solid rgba(157, 61, 24, 0.22);
  background: white;
  border-radius: 999px;
  padding: 0.45rem 0.9rem;
  cursor: pointer;
  font: inherit;
  color: var(--ink);
}

.mode-toggle.is-active {
  background: var(--accent-soft);
  border-color: rgba(157, 61, 24, 0.38);
}

.toc-shell {
  margin: 1rem 0 1.4rem;
  overflow: hidden;
}

.toc-shell summary {
  cursor: pointer;
  padding: 1rem 1.2rem;
  font-size: 1.05rem;
  list-style: none;
}

.toc-shell summary::-webkit-details-marker {
  display: none;
}

.toc-shell summary::after {
  content: "+";
  float: right;
  color: var(--accent);
}

.toc-shell[open] summary::after {
  content: "-";
}

.toc-copy {
  padding: 0 1.2rem 1.2rem;
  border-top: 1px solid var(--line);
}

.chaos-toc {
  column-width: 18rem;
  column-gap: 2rem;
  padding-left: 1.4rem;
}

.chaos-toc li {
  break-inside: avoid;
  margin-bottom: 0.45rem;
}

.featured-shell {
  display: grid;
  gap: 1rem;
}

.cover-figure {
  margin: 0 0 1.2rem;
}

.cover-figure img {
  display: block;
  width: 100%;
  max-width: 520px;
  margin: 0 auto;
  border-radius: 24px;
  border: 1px solid var(--line);
  box-shadow: 0 20px 50px rgba(69, 47, 30, 0.10);
  background: rgba(255, 255, 255, 0.55);
}

.cover-figure figcaption {
  display: none;
}

.featured-meta {
  padding: 0.2rem 0 0;
}

.featured-link-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.featured-story h1:first-child {
  display: none;
}

.story-nav {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.8rem;
  padding: 0;
  margin-top: 1rem;
  background: transparent;
  border: 0;
  box-shadow: none;
}

.story-nav a {
  background: var(--accent-soft);
  border: 1px solid rgba(157, 61, 24, 0.18);
  border-radius: 999px;
  padding: 0.5rem 0.9rem;
  text-decoration: none;
}

.story-nav [data-nav="prev"] {
  margin-right: auto;
}

.story-nav [data-nav="home"] {
  margin: 0 auto;
}

.story-nav [data-nav="next"] {
  margin-left: auto;
}

.story-id {
  width: 100%;
  text-align: center;
}

h1, h2, h3, h4 {
  line-height: 1.2;
}

h1 {
  margin-top: 0;
  font-size: clamp(2rem, 5vw, 3rem);
}

h2 {
  margin-top: 2.2rem;
  padding-top: 0.4rem;
  border-top: 1px solid var(--line);
}

a {
  color: var(--accent);
}

blockquote {
  margin: 1.5rem 0;
  padding: 0.2rem 1rem;
  border-left: 4px solid var(--accent);
  background: rgba(157, 61, 24, 0.05);
}

pre, code {
  font-family: "SFMono-Regular", Menlo, Consolas, monospace;
}

pre {
  overflow-x: auto;
  padding: 1rem;
  border-radius: 12px;
  background: #241d19;
  color: #f5eee6;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
}

th, td {
  border: 1px solid var(--line);
  padding: 0.55rem 0.7rem;
  text-align: left;
  vertical-align: top;
}

th {
  background: rgba(157, 61, 24, 0.08);
}

ul, ol {
  padding-left: 1.4rem;
}

hr {
  border: 0;
  border-top: 1px solid var(--line);
  margin: 2rem 0;
}

@media (max-width: 640px) {
  .content {
    padding: 1.2rem;
  }

  .control-shell {
    grid-template-columns: 1fr;
  }

  .story-id {
    order: 4;
  }
}
"""


def build_runtime_script(manifest: list[dict[str, str]]) -> str:
    manifest_json = json.dumps(manifest, ensure_ascii=False)
    return f"""<script>
const STORY_MANIFEST = {manifest_json};
const STORAGE_MODE_KEY = "last_things_mode";
const STORAGE_SHUFFLE_KEY = "last_things_shuffle";
const STORAGE_FONT_KEY = "last_things_font_size";

function makeShuffle(items) {{
  const copy = items.slice();
  for (let i = copy.length - 1; i > 0; i -= 1) {{
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }}
  return copy;
}}

function loadMode() {{
  const mode = localStorage.getItem(STORAGE_MODE_KEY);
  return mode === "ordered" ? "ordered" : "shuffle";
}}

function saveMode(mode) {{
  localStorage.setItem(STORAGE_MODE_KEY, mode);
}}

function loadShuffleOrder() {{
  try {{
    const raw = localStorage.getItem(STORAGE_SHUFFLE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (!Array.isArray(parsed) || parsed.length !== STORY_MANIFEST.length) {{
      throw new Error("bad order");
    }}
    const names = new Set(STORY_MANIFEST.map((item) => item.file));
    if (!parsed.every((file) => names.has(file))) {{
      throw new Error("bad names");
    }}
    return parsed;
  }} catch (_error) {{
    const shuffled = makeShuffle(STORY_MANIFEST.map((item) => item.file));
    localStorage.setItem(STORAGE_SHUFFLE_KEY, JSON.stringify(shuffled));
    return shuffled;
  }}
}}

function getOrderedFiles(mode) {{
  if (mode === "ordered") {{
    return STORY_MANIFEST.map((item) => item.file);
  }}
  return loadShuffleOrder();
}}

function loadFontScale() {{
  const raw = Number(localStorage.getItem(STORAGE_FONT_KEY));
  if (!Number.isFinite(raw)) return 15;
  return Math.min(24, Math.max(15, raw));
}}

function saveFontScale(scale) {{
  localStorage.setItem(STORAGE_FONT_KEY, String(scale));
}}

function applyFontScale(scale) {{
  document.querySelectorAll(".content").forEach((node) => {{
    node.style.fontSize = `${{scale}}px`;
  }});
  const value = document.querySelector("[data-font-value]");
  if (value) {{
    value.textContent = String(scale);
  }}
}}

function entryByFile(file) {{
  return STORY_MANIFEST.find((item) => item.file === file);
}}

function wireModeButtons() {{
  const buttons = document.querySelectorAll("[data-mode]");
  const toc = document.querySelector("[data-chaos-toc]");
  const featureTitle = document.querySelector("[data-feature-title]");
  const featureLink = document.querySelector("[data-feature-link]");
  const featureBody = document.querySelector("[data-feature-body]");
  const nav = document.querySelector("[data-feature-nav]");

  function render(mode) {{
    saveMode(mode);
    const files = getOrderedFiles(mode);
    buttons.forEach((button) => {{
      button.classList.toggle("is-active", button.dataset.mode === mode);
    }});

    if (toc) {{
      const items = files.map((file, index) => {{
        const entry = entryByFile(file);
        return `<li><a href="body/${{entry.file}}">${{entry.title}}</a> <span class="toc-id">#${{String(index + 1).padStart(3, "0")}}</span></li>`;
      }});
      toc.innerHTML = items.join("");
    }}

    if (featureTitle && featureLink && featureBody && nav && files.length) {{
      const current = entryByFile(files[0]);
      const previous = entryByFile(files[files.length - 1]);
      const next = entryByFile(files[1] || files[0]);
      featureTitle.textContent = current.title;
      featureLink.href = `body/${{current.file}}`;
      featureBody.innerHTML = current.excerpt;
      nav.querySelector('[data-nav="prev"]').href = `body/${{previous.file}}`;
      nav.querySelector('[data-nav="next"]').href = `body/${{next.file}}`;
    }}
  }}

  buttons.forEach((button) => {{
    button.addEventListener("click", () => {{
      if (button.dataset.mode === "shuffle" && button.dataset.refresh === "true") {{
        localStorage.removeItem(STORAGE_SHUFFLE_KEY);
      }}
      render(button.dataset.mode);
    }});
  }});

  render(loadMode());
}}

function wireStoryNav() {{
  const storyFile = document.body.dataset.storyFile;
  if (!storyFile) return;
  const mode = loadMode();
  const files = getOrderedFiles(mode);
  const index = files.indexOf(storyFile);
  if (index === -1) return;
  const previous = entryByFile(files[(index - 1 + files.length) % files.length]);
  const next = entryByFile(files[(index + 1) % files.length]);
  const nav = document.querySelector("[data-story-nav]");
  if (!nav) return;
  nav.querySelector('[data-nav="prev"]').href = previous.file;
  nav.querySelector('[data-nav="next"]').href = next.file;
  const label = nav.querySelector("[data-story-id]");
  if (label) {{
    label.textContent = `${{mode === "shuffle" ? "Shuffled" : "Ordered"}} · #${{String(index + 1).padStart(3, "0")}}`;
  }}
}}

function wireFontTools() {{
  const minus = document.querySelector('[data-font-step="-1"]');
  const plus = document.querySelector('[data-font-step="1"]');
  applyFontScale(loadFontScale());
  [minus, plus].forEach((button) => {{
    if (!button) return;
    button.addEventListener("click", () => {{
      const direction = Number(button.dataset.fontStep);
      const next = Math.min(24, Math.max(15, loadFontScale() + direction));
      saveFontScale(next);
      applyFontScale(next);
    }});
  }});
}}

function forceCollapsedToc() {{
  const toc = document.querySelector(".toc-shell");
  if (toc) {{
    toc.open = false;
  }}
}}

wireModeButtons();
wireFontTools();
forceCollapsedToc();
wireStoryNav();
</script>"""


def build_index_page(manifest: list[dict[str, str]], script: str) -> str:
    first = manifest[0]
    content = f"""
<section class="control-shell">
  <span class="mode-label">Reading order:</span>
  <button class="mode-toggle" data-mode="ordered" type="button" title="This front page opens on the numbered manuscript order. The order below follows the book's file sequence.">In Order</button>
  <button class="mode-toggle" data-mode="shuffle" data-refresh="false" type="button" title="This front page opens on a shuffled path through the manuscript. The order below is intentionally unstable.">Shuffle</button>
  <button class="mode-toggle" data-mode="shuffle" data-refresh="true" type="button" title="Generate a fresh stochastic path for this reader and redraw the front page in a new unstable order.">Stochastic</button>
</section>

<details class="toc-shell">
  <summary>Table of Contents</summary>
  <div class="toc-copy">
    <p>Folded by default, as a courtesy to accidents.</p>
    <ol class="chaos-toc" data-chaos-toc></ol>
    <p class="toc-meta">The manuscript source order still lives in <code>main.md</code>. This page prefers drift.</p>
  </div>
</details>

<section class="featured-shell">
  <figure class="cover-figure">
    <img src="cover.png" alt="A red and cream drawing of a man pushing a stone uphill while earlier versions of him lie crushed below in an endless cycle.">
  </figure>
  <div class="featured-meta">
    <p class="eyebrow">Opening chapter</p>
    <h2 data-feature-title>{html.escape(first["title"])}</h2>
    <div class="featured-link-row">
      <p><a data-feature-link href="body/{html.escape(first["file"], quote=True)}">Open this chapter on its own page</a></p>
      <div class="reader-tools">
        <span class="tool-label">Text</span>
        <button class="tool-button" type="button" data-font-step="-1" title="Decrease text size">-</button>
        <span class="tool-value" data-font-value>15</span>
        <button class="tool-button" type="button" data-font-step="1" title="Increase text size">+</button>
      </div>
    </div>
  </div>
  <article class="content featured-story" data-feature-body>
    {first["excerpt"]}
  </article>
  <nav class="story-nav" data-feature-nav>
    <a data-nav="prev" href="body/{html.escape(first["file"], quote=True)}">Previous</a>
    <a data-nav="home" href="index.html">Home</a>
    <a data-nav="next" href="body/{html.escape(first["file"], quote=True)}">Next</a>
  </nav>
</section>

<p class="copyright-note">Copyright © Zheng Pei.</p>
"""
    return page_template(TITLE, content, script=script)


def build_story_page(source: Path, script: str) -> str:
    title = slug_to_title(source)
    content = md_to_html(source.read_text(encoding="utf-8"))
    nav = """
<nav class="story-nav" data-story-nav>
  <a data-nav="prev" href="#">Previous</a>
  <a data-nav="home" href="../index.html">Home</a>
  <a data-nav="next" href="#">Next</a>
  <span class="story-id" data-story-id></span>
</nav>
"""
    full = f'<article class="content">{content}</article>{nav}'
    body_attrs = f'data-story-file="{html.escape(source.name[:-3] + ".html", quote=True)}"'
    return page_template(title, full, nested=True, body_attrs=body_attrs, script=script)


def render_static_page(source: Path, destination: Path, title: str) -> None:
    content = md_to_html(source.read_text(encoding="utf-8"))
    destination.write_text(page_template(title, f'<article class="content">{content}</article>'), encoding="utf-8")


if HTML_DIR.exists():
    shutil.rmtree(HTML_DIR)
HTML_BODY_DIR.mkdir(parents=True, exist_ok=True)

(HTML_DIR / "style.css").write_text(STYLE.strip() + "\n", encoding="utf-8")
(HTML_DIR / "cover.png").write_bytes((ROOT / "cover.png").read_bytes())
shutil.copytree(ROOT / "figures", HTML_DIR / "figures")

body_files = sorted(BODY_DIR.glob("*.md"))
manifest: list[dict[str, str]] = []
for source in body_files:
    title = slug_to_title(source)
    excerpt = md_to_html(source.read_text(encoding="utf-8"))
    manifest.append(
        {
            "file": f"{source.stem}.html",
            "title": title,
            "excerpt": excerpt,
        }
    )

runtime_script = build_runtime_script(manifest)

(HTML_DIR / "index.html").write_text(build_index_page(manifest, runtime_script), encoding="utf-8")
render_static_page(ROOT / "README.md", HTML_DIR / "readme.html", "README")
render_static_page(ROOT / "LICENSE.md", HTML_DIR / "license.html", "License")

for source in body_files:
    destination = HTML_BODY_DIR / f"{source.stem}.html"
    destination.write_text(build_story_page(source, runtime_script), encoding="utf-8")

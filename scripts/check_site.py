"""Check generated HTML, local links, and search metadata without network dependencies."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
# Pages that must not be indexed or listed in the sitemap.
NOT_INDEXED = {"404.html"}


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self.ids: set[str] = set()
        self.meta: dict[str, str] = {}
        self.canonical: str | None = None
        self.title = ""
        self.json_ld: list[str] = []
        self._in_title = False
        self._in_json_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value for key, value in attrs if value is not None}
        for key, value in values.items():
            if key == "id" or (tag == "a" and key == "name"):
                self.ids.add(value)
            if key in {"href", "src"}:
                self.urls.append(value)
        if tag == "meta" and "content" in values:
            name = values.get("name") or values.get("property")
            if name:
                self.meta[name] = values["content"]
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href")
        self._in_title = tag == "title"
        if tag == "script" and values.get("type") == "application/ld+json":
            self._in_json_ld = True
            self.json_ld.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_json_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_json_ld:
            self.json_ld[-1] += data


def site_url(config: Path) -> str:
    # Plain, single- or double-quoted scalar, optionally followed by a comment.
    match = re.search(
        r"""^url:[ \t]*(["']?)([^"'\s#]+)\1[ \t]*(?:#.*)?$""",
        config.read_text(encoding="utf-8"),
        re.M,
    )
    if not match:
        raise SystemExit(f"No url in {config}")
    return match.group(2).rstrip("/")


def page_url(base: str, root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    if relative == "index.html":
        return base + "/"
    if relative.endswith("/index.html"):
        return f"{base}/{relative[: -len('index.html')]}"
    return f"{base}/{relative}"


def check_links(root: Path, pages: dict[Path, Page]) -> list[str]:
    errors = []
    for path, page in pages.items():
        for value in page.urls:
            url = urlsplit(value)
            if url.scheme or url.netloc:
                continue
            relative = unquote(url.path)
            target = (
                root / relative.lstrip("/")
                if relative.startswith("/")
                else path.parent / relative if relative else path
            ).resolve()
            if not target.is_relative_to(root):
                errors.append(f"{path.relative_to(root)}: link escapes site: {value}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{path.relative_to(root)}: missing target: {value}")
            elif url.fragment and target in pages:
                if unquote(url.fragment) not in pages[target].ids:
                    errors.append(f"{path.relative_to(root)}: missing anchor: {value}")
    return errors


def check_metadata(base: str, root: Path, pages: dict[Path, Page]) -> list[str]:
    errors = []
    for path, page in pages.items():
        name = path.relative_to(root).as_posix()
        robots = page.meta.get("robots", "")
        if name in NOT_INDEXED:
            if "noindex" not in robots:
                errors.append(f"{name}: expected noindex")
            continue
        if "noindex" in robots:
            errors.append(f"{name}: unexpected noindex")
        if not page.title.strip():
            errors.append(f"{name}: empty title")
        if not page.meta.get("description", "").strip():
            errors.append(f"{name}: missing meta description")
        if page.canonical != page_url(base, root, path):
            errors.append(f"{name}: canonical {page.canonical!r} does not match page URL")
        for block in page.json_ld:
            try:
                json.loads(block)
            except json.JSONDecodeError as error:
                errors.append(f"{name}: invalid JSON-LD: {error}")
    return errors


def check_sitemap(base: str, root: Path, pages: dict[Path, Page]) -> list[str]:
    try:
        tree = ET.parse(root / "sitemap.xml")
    except ET.ParseError as error:
        return [f"sitemap.xml: invalid XML: {error}"]
    errors = []
    listed = {loc.text or "" for loc in tree.iter(f"{SITEMAP_NS}loc")}
    expected = {
        page_url(base, root, path)
        for path in pages
        if path.relative_to(root).as_posix() not in NOT_INDEXED
    }
    for url in sorted(listed - expected):
        errors.append(f"sitemap.xml: URL without an indexable page: {url}")
    for url in sorted(expected - listed):
        errors.append(f"sitemap.xml: page missing from sitemap: {url}")
    return errors


def check_robots(base: str, root: Path) -> list[str]:
    lines = [line.strip() for line in (root / "robots.txt").read_text(encoding="utf-8").splitlines()]
    errors = []
    if f"Sitemap: {base}/sitemap.xml" not in lines:
        errors.append("robots.txt: missing absolute Sitemap line")
    if "Disallow: /" in lines:
        errors.append("robots.txt: blocks the whole site")
    return errors


def check_feed(root: Path) -> list[str]:
    try:
        ET.parse(root / "feed.xml")
    except ET.ParseError as error:
        return [f"feed.xml: invalid XML: {error}"]
    return []


def check(root: Path, config: Path) -> list[str]:
    root = root.resolve()
    required = ("index.html", "404.html", "sitemap.xml", "feed.xml", "robots.txt")
    missing = [f"Missing {name}" for name in required if not (root / name).is_file()]
    if missing:
        return missing
    base = site_url(config)
    pages = {}
    for path in root.rglob("*.html"):
        page = Page()
        page.feed(path.read_text(encoding="utf-8"))
        pages[path] = page
    return (
        check_links(root, pages)
        + check_metadata(base, root, pages)
        + check_sitemap(base, root, pages)
        + check_robots(base, root)
        + check_feed(root)
    )


if __name__ == "__main__":
    failures = check(Path(sys.argv[1] if len(sys.argv) > 1 else "_site"), Path("_config.yml"))
    if failures:
        print("\n".join(failures), file=sys.stderr)
        sys.exit(1)
    print("Generated pages, local links, and search metadata passed.")

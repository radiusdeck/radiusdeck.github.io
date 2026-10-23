"""Check generated HTML and local file links without network dependencies."""

from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if value is None:
                continue
            if key == "id" or (tag == "a" and key == "name"):
                self.ids.add(value)
            if key in {"href", "src"}:
                self.urls.append(value)


def check(root: Path) -> list[str]:
    root = root.resolve()
    errors = []
    for required in ("index.html", "404.html"):
        if not (root / required).is_file():
            errors.append(f"Missing {required}")
    pages = {}
    for path in root.rglob("*.html"):
        parser = Links()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[path] = parser
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


if __name__ == "__main__":
    failures = check(Path(sys.argv[1] if len(sys.argv) > 1 else "_site"))
    if failures:
        print("\n".join(failures), file=sys.stderr)
        sys.exit(1)
    print("Generated pages and local links passed.")

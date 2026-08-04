import re
from pathlib import Path

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
_HEADING_RE = re.compile(r"^## (v\S+)\s*$", re.MULTILINE)


def get_version(changelog_path: Path | str = CHANGELOG_PATH) -> str:
    try:
        text = Path(changelog_path).read_text(encoding="utf-8")
    except OSError:
        return "dev"
    match = _HEADING_RE.search(text)
    return match.group(1) if match else "dev"

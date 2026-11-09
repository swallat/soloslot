"""Turn THIRD_PARTY_NOTICES.md into plain text for the Windows installer info page.

Inno Setup shows the file as-is, so Markdown marks would be visible. Usage:
    python packaging/notices_txt.py <output.txt>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src/soloslot/gui/assets/THIRD_PARTY_NOTICES.md"


def to_plain(markdown: str) -> str:
    lines = []
    for line in markdown.splitlines():
        heading = re.match(r"(#+)\s+(.*)", line)
        if heading:
            title = heading.group(2).replace("**", "")
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(title.upper() if len(heading.group(1)) <= 2 else title)
            lines.append("-" * len(title) if len(heading.group(1)) <= 2 else "")
            if len(heading.group(1)) > 2:
                lines.pop()
            continue
        line = re.sub(r"<(https?://[^>\s]+)>", r"\1", line)
        line = line.replace("**", "").replace("`", "")
        lines.append(line)
    return "\r\n".join(lines).strip() + "\r\n"


def main() -> None:
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(to_plain(SOURCE.read_text("utf-8")).encode("utf-8-sig"))


if __name__ == "__main__":
    main()

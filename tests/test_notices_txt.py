import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "notices_txt", Path(__file__).resolve().parents[1] / "packaging/notices_txt.py"
)
notices_txt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notices_txt)


def test_installer_text_has_no_markdown_marks():
    text = notices_txt.to_plain(notices_txt.SOURCE.read_text("utf-8"))
    assert "**" not in text
    assert "<http" not in text
    assert not any(line.startswith("#") for line in text.splitlines())
    assert "LICENSES" in text
    assert "https://github.com/swallat/soloslot/blob/main/LICENSE" in text

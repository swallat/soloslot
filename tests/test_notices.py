import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
NOTICES = (ROOT / "src/soloslot/gui/assets/THIRD_PARTY_NOTICES.md").read_text("utf-8").lower()


def test_every_dependency_is_listed_in_the_notices():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    requirements = list(project["dependencies"])
    for extra in project["optional-dependencies"].values():
        requirements += extra
    for requirement in requirements:
        name = re.split(r"[<>=!~\[ ;]", requirement, maxsplit=1)[0].lower()
        name = name.removesuffix("-essentials")  # PySide6-Essentials is covered by "PySide6"
        assert name in NOTICES, f"{name} is missing in THIRD_PARTY_NOTICES.md"

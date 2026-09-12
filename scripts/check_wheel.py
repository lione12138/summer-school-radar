"""Build a wheel and verify assets and rendering outside the source checkout."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    with TemporaryDirectory(prefix="summa-wheel-") as temporary:
        directory = Path(temporary)
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(directory), str(ROOT)],
                       check=True)
        wheel = next(directory.glob("summer_school_radar-*.whl"))
        extracted = directory / "installed"
        with ZipFile(wheel) as archive:
            expected = {
                path.relative_to(ROOT / "src").as_posix()
                for path in (ROOT / "src/research_school_radar/web").rglob("*") if path.is_file()
            }
            missing = expected - set(archive.namelist())
            if missing:
                raise RuntimeError(f"Wheel is missing public assets: {sorted(missing)}")
            archive.extractall(extracted)
        # -I and a temporary cwd ensure editable-install paths cannot hide
        # missing modules or resources in the actual distribution.
        code = '''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from research_school_radar.site_assets import _TEMPLATES
from research_school_radar.site_programme import render_programme_page
for name in _TEMPLATES.list_templates():
    _TEMPLATES.get_template(name)
html = render_programme_page({"id": "test", "slug": "test", "title": "Example school",
    "editions": [{"title": "Example edition", "start_date": "2099-01-01", "duration_days": 5,
                   "detail_path": "opportunities/example.html"}]}, {})
assert "Example edition" in html
print("Wheel assets and isolated programme rendering validated.")
'''
        subprocess.run([sys.executable, "-I", "-c", code, str(extracted)], cwd=directory, check=True)


if __name__ == "__main__":
    main()

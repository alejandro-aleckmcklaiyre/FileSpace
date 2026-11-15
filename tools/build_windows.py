"""Build the approved folder-based Windows package without touching user data."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project = Path(__file__).resolve().parents[1]
    if os.name != "nt":
        raise SystemExit("Build Windows executables on Windows.")
    distribution, work = (project / "dist").resolve(), (project / "build").resolve()
    if not all(path.is_relative_to(project) and path != project for path in (distribution, work)):
        raise SystemExit("Build output must resolve inside this project; external junctions are not allowed.")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(distribution), "--workpath", str(work), "FileSpace.spec",
    ], cwd=project, check=True)
    package = project / "dist/FileSpace"
    documentation = package / "docs"
    documentation.mkdir(exist_ok=True)
    for name in ("USER_GUIDE.md", "WINDOWS_BUILD.md", "KNOWN_LIMITATIONS.md", "ACCEPTANCE_TESTS.md"):
        shutil.copy2(project / "docs" / name, documentation / name)
    shutil.copy2(project / "THIRD_PARTY_NOTICES.txt", package / "THIRD_PARTY_NOTICES.txt")
    entries = []
    for path in sorted(package.rglob("*")):
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            entries.append({"path": path.relative_to(package).as_posix(), "bytes": path.stat().st_size, "sha256": digest})
    report = {"python": sys.version, "platform": sys.platform, "files": entries}
    (project / "build/package-manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Built {package / 'FileSpace.exe'} ({sum(item['bytes'] for item in entries):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

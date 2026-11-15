"""Archive the complete local build for review; never upload or publish it."""

import hashlib
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.version import VERSION


def main() -> int:
    project = Path(__file__).resolve().parents[1]
    package = project / "dist/FileSpace"
    if not (package / "FileSpace.exe").is_file():
        raise SystemExit("Build FileSpace first.")
    archive = project / f"dist/FileSpace-{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                output.write(path, Path("FileSpace") / path.relative_to(package))
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"Created {archive} ({archive.stat().st_size:,} bytes)\nSHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

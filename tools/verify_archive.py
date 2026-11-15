"""Extract a local review archive elsewhere and verify its executable."""

import argparse
import tempfile
import zipfile
from pathlib import Path

from verify_package import verify


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path("dist/FileSpace-1.0.0-preview-windows-x64.zip"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/relocated-smoke.json"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="filespace-relocated-") as folder:
        root = Path(folder).resolve()
        with zipfile.ZipFile(args.archive) as archive:
            for entry in archive.infolist():
                target = (root / entry.filename).resolve()
                if not target.is_relative_to(root):
                    raise SystemExit("Archive contains a path outside its extraction directory.")
            archive.extractall(root)
        return verify(root / "FileSpace/FileSpace.exe", args.report)


if __name__ == "__main__":
    raise SystemExit(main())

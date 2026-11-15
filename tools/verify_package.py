"""Launch the executable from an unrelated directory with Python/Qt env cleared."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def verify(executable: Path, report: Path) -> int:
    executable, report = executable.resolve(), report.resolve()
    if report.exists():
        raise SystemExit(f"Choose a new report path; {report} already exists.")
    environment = dict(os.environ)
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"):
        environment.pop(name, None)
    windows = Path(environment.get("SystemRoot", "C:/Windows"))
    environment["PATH"] = os.pathsep.join([str(windows / "System32"), str(windows)])
    with tempfile.TemporaryDirectory(prefix="filespace-launch-") as folder:
        result = subprocess.run([str(executable), "--smoke-test", str(report)], cwd=folder, env=environment, timeout=180, check=False)
    data = json.loads(report.read_text(encoding="utf-8"))
    if result.returncode or not data.get("passed") or not data.get("frozen"):
        print(json.dumps(data, indent=2))
        return 1
    print(f"PASS: {len(data['checks'])} packaged checks; frozen imports; clean environment; report {report}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, default=Path("dist/FileSpace/FileSpace.exe"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/packaged-smoke.json"))
    args = parser.parse_args()
    return verify(args.executable, args.report)


if __name__ == "__main__":
    raise SystemExit(main())

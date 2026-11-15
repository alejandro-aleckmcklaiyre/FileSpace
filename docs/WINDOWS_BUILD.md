# Build and verify the Windows package

Build on Windows using the project's Python 3.14 development environment. This
build was validated with Python 3.14.7 x64, PySide6 6.12.0 and PyInstaller 6.22.3.
The PRD permits Python 3.12+, but other combinations need their own verification.

Install runtime and pinned development tools in the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run the test suite, lint, and package consistency checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests tools
.\.venv\Scripts\python.exe -m pip check
```

Build the onedir Windows application:

```powershell
.\.venv\Scripts\python.exe tools/build_windows.py
```

The script uses `FileSpace.spec`, including icon/version resources, Qt hooks,
runtime assets, and upstream package license/metadata files. It refreshes generated
`build`/`dist` output within this project; do not store personal files there.
`build/package-manifest.json` records every output file's size and SHA-256.

Verify the executable using a **new** report filename:

```powershell
.\.venv\Scripts\python.exe tools/verify_package.py --report artifacts/packaged-smoke.json
```

The launcher clears Python/virtual-environment/Qt variables, limits PATH to Windows
directories, and launches from a separate temporary working directory. The program
uses `--smoke-test` to generate its own fixtures and isolated database, exercises
the GUI and workers, checks frozen imports, then exits. No existing user files,
clipboard, Recycle Bin entries, or settings are used by those checks. Report
creation refuses to overwrite an existing file. New filenames are required on reruns.

The 11 packaged checks cover window/icon/layout, image/PDF/text/DOCX/XLSX/PPTX,
decoded video frames, verified copy/move/rename/history, persistence after restart,
resource/module isolation, and executable-folder protection. Video uses a committed
generated fixture; an external FFmpeg executable is not required at runtime.

Create the local review ZIP after a successful verification:

```powershell
.\.venv\Scripts\python.exe tools/archive_windows.py
```

Extract the ZIP elsewhere and rerun `tools/verify_package.py --executable` against
the extracted executable with another report name. This checks archive portability;
a genuinely clean Windows machine without Python still requires manual acceptance.

Or automate extraction into a disposable temporary directory and verification:

```powershell
.\.venv\Scripts\python.exe tools/verify_archive.py --report artifacts/relocated-smoke.json
```

## Files to review

- `dist/FileSpace/`: complete runnable folder, including `_internal`.
- `dist/FileSpace-1.0.0-preview.2-windows-x64.zip`: review archive.
- The adjacent `.sha256`: archive integrity hash.
- `artifacts/packaged-smoke.json`: measured packaged check results.
- `build/FileSpace/warn-FileSpace.txt`: dependency analyzer warnings.
- `build/package-manifest.json`: output hashes.
- `docs/MILESTONE_8_REPORT.md`: findings and remaining manual checks.

Generated binaries, build data, and reports are ignored by Git. Building does not
publish a release, create an installer, merge a branch, or upload anything.

## Known build details

The Windows GUI subsystem executable has no console and requests normal user
privileges (`asInvoker`). Runtime failures are logged locally. Frozen Open actions
temporarily clear the bundle's Windows DLL search directory when invoking external
associations, then restore it. Protected paths include both the executable folder
and its internal bundled libraries.

Ruff checks syntax/imports and selected bug-prevention rules. Deliberate parser
and worker exception boundaries remain broad to keep errors inside UI workflows;
they are reviewed and reported rather than silently treated as success.

PyInstaller warning entries for POSIX-only modules and unused optional HTML/image
plugins are not all install requirements. The packaged smoke run establishes the
tested imports/features; it does not establish every optional codec/plugin.

References: [PyInstaller runtime paths](https://pyinstaller.org/en/stable/runtime-information.html)
and [external-launch DLL handling](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html).

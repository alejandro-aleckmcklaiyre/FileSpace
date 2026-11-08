# FileSpace

A local Windows desktop file manager built with Python and PySide6.
See [the PRD](docs/PRD.md) for the product requirements and milestones.

## Current scope

Milestone 4 provides read-only browsing and integrated file previews in **FileSpace**, initially
1200 × 800 logical pixels, with a navigation bar, scrollable sidebar, empty
file details view, and preview panel. Drag the dividers to resize panels.
Select a sidebar folder or drive to browse it. The Preview button hides
and restores the preview panel, preserving its previous proportions.

Back, Forward, Up, Refresh, and address entry work. Double-click folders to open
them; double-clicking files does not launch an external application. Relative
paths are interpreted against the current folder. Refresh reloads the listing
and available drives. Standard folders use Windows/Qt locations, including
redirected folders. Hidden/system entries follow Qt's default visibility.

The listing displays name, type, size, and modification date. It reads directory
metadata. Selecting a file reads its preview without modifying it. Search,
Quick Sort, storage, and file operations belong to later milestones.
Invalid or inaccessible destinations show a warning and preserve the last valid
location and history. If a drive disconnects after loading, Refresh or navigating
back to it checks access again; continuous drive-disconnection notifications are
not implemented. Directory validation uses a worker and Qt loads listings
asynchronously. OS/network requests can still take time to finish.

## Previews

- Images: JPG/JPEG, PNG, WEBP, BMP, GIF (first frame only), scaled to fit.
- PDF: embedded QtPdf-rendered pages with Previous/Next controls. Password-protected
  PDFs show an error; password entry is not implemented.
- Video: MP4, MKV, MOV, AVI through QtMultimedia. Press Play to start; pause and
  seeking controls are provided. Codec support varies. Duration appears when available.
- TXT/LOG/CSV: plain text, not an interpreted document or CSV spreadsheet.
- DOCX: paragraph text; embedded images, tables, headers, and formatting omitted.
- PPTX: text-frame content labeled by slide; images and full slide layout omitted.
- XLSX: first worksheet, first 100 rows and 20 columns, cached formula values only
  (formulas are not calculated). Cells are limited to 1,000 characters.

Metadata includes name, extension, size, modified time, location, image dimensions,
and video duration where available. Unsupported/corrupt/inaccessible files show
messages rather than crashing. Previews are read-only and never execute macros.

Bounds: text reads 100,000 bytes (UTF-8/UTF-16 BOM support; invalid bytes are
replaced); Office text shows up to 100,000 characters / 5,000 blocks; Office files
are limited to 20 MiB compressed and 64 MiB expanded / 5,000 ZIP entries; PDF
files are limited to 50 MiB, rendering one page at up to 1200 × 1600 pixels;
images are checked against 40 million source pixels and decoded at up to
1600 × 1600 pixels. Qt's own image allocation limit also applies.

Blocking extraction/rendering runs on a worker. Rapid selection changes coalesce
to the latest request; stale results are discarded. A running parser cannot be
forcibly interrupted, so the next preview may wait for it to finish. These limits
reduce resource use but are not a sandbox for untrusted parsers. Hiding the panel,
changing selection, or closing the window releases displayed content and stops
video; showing it again reloads the selected preview. Only one file previews at a time.

## Development setup (PowerShell)

Use Windows 10/11, Python 3.14 (validated locally with 3.14.7), and Git.
The PRD permits Python 3.12+, but other Python versions have not been verified.
Run commands from the FileSpace project folder.

Create a virtual environment to isolate project packages:

```powershell
py -3.14 -m venv .venv
```

Install the recorded dependencies into that environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

In VS Code, use **Python: Select Interpreter** and select
`.venv\Scripts\python.exe`. Activation is optional; the commands here call
the environment's interpreter directly, avoiding activation-policy issues.

## Run

Start the application; close its window to return to the terminal:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Verify

Check package consistency:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Check Qt's window, PDF, and multimedia modules:

```powershell
.\.venv\Scripts\python.exe -c "from PySide6 import QtCore, QtWidgets, QtPdf, QtPdfWidgets, QtMultimedia, QtMultimediaWidgets; print('Qt version:', QtCore.qVersion()); print('Required Qt imports passed')"
```

Launch the app and confirm the title, resizing, normal closing, and absence of
tracebacks. Windows display scaling may change its physical pixel dimensions.
For Milestone 2, also check sidebar selection, panel dividers, preview hiding
and restoration, and sidebar scrolling at the minimum window height.
For Milestone 3, check each available drive, standard folders, direct paths,
double-click folder navigation, Back/Forward, Up at a drive root, and Refresh.
Try a nonexistent path and a disconnected removable drive; the current location
must remain unchanged after an error. Check a large folder for responsiveness.

Run automated browsing and preview checks in temporary folders (standard-library unittest,
no additional test package required):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

These checks cover history, invalid/permission-denied paths, relative paths,
root navigation, stale navigation results, listing refresh, and read-only UI
settings. Real removable-drive disconnection and Windows ACL behavior still
require manual checks; permission denial is simulated in the automated check.
Preview checks generate image, PDF, and Office fixtures and cover text bounds,
corrupt/unsupported files, simulated permission errors, stale results, and cleanup.
If FFmpeg is already on PATH, an optional test generates temporary videos in all
four supported containers and checks decoded frames. FFmpeg is not required to
run FileSpace. Manually inspect visual quality, sound, seeking, large documents,
and your own video codecs. Select files rapidly and toggle Preview during loading.

If imports fail, check that VS Code and the terminal use the same environment.
Download failures can indicate a network/proxy restriction. Qt DLL errors
require checking Python architecture, installation completeness, and conflicting
Qt environment variables. Administrator privileges are not required to run
FileSpace.

## Project layout

- `main.py`: thin launcher.
- `app/main.py`: application initialization and event loop.
- `app/ui/main_window.py`: desktop window, separate from future file operations.
- `app/ui/navigation_bar.py`: navigation controls and preview toggle signal.
- `app/ui/sidebar.py`: scrollable location choices and destination sections.
- `app/ui/file_explorer.py`: read-only Qt filesystem model and details view.
- `app/ui/preview_panel.py`: preview content, metadata, pagination, and media controls.
- `app/services/file_preview_service.py`: worker dispatch and stale-result handling.
- `app/previews/`: bounded text, Office, image, and PDF handlers.
- `app/services/file_browser_service.py`: worker validation and navigation history.
- `app/services/drive_service.py`: Qt standard folders and mounted volumes.
- `app/filesystem/path_validator.py`: read-only path/access validation.
- `tests/test_browsing.py`: disposable-folder browsing regression checks.
- `tests/test_previews.py`: generated-fixture preview and optional video checks.
- `docs/PRD.md`: product requirements.
- `requirements.txt`: pinned environment dependencies, including Qt support packages.
- Office extraction uses `python-docx`, `openpyxl`, and `python-pptx`; their
  supporting packages are also pinned in `requirements.txt`.
- `.gitignore`: excludes the local environment, caches, and build output.

Review changes before committing. Commits require approval; verify the intended
account and repository before any remote push.

Qt references: [PDF document rendering](https://doc.qt.io/qtforpython-6/PySide6/QtPdf/QPdfDocument.html)
and [image decoding limits](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QImageReader.html).

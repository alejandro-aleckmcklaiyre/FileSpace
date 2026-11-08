# FileSpace

A local Windows desktop file manager built with Python and PySide6.
See [the PRD](docs/PRD.md) for the product requirements and milestones.

## Current scope

Milestone 5 adds persistent Quick Sort destinations and confirmed file moves to **FileSpace**, initially
1200 × 800 logical pixels, with a navigation bar, scrollable sidebar,
file details view, and preview panel. Drag the dividers to resize panels.
Select a sidebar folder or drive to browse it. The Preview button hides
and restores the preview panel, preserving its previous proportions.

Back, Forward, Up, Refresh, and address entry work. Double-click folders to open
them; double-clicking files does not launch an external application. Relative
paths are interpreted against the current folder. Refresh reloads the listing
and available drives. Standard folders use Windows/Qt locations, including
redirected folders. Hidden/system entries follow Qt's default visibility.

The listing displays name, type, size, and modification date. It reads directory
metadata. Selecting a file reads its preview without modifying it. The browsing
model remains read-only; only confirmed Quick Sort operations transfer files.
Search, drag-and-drop, general file commands, and undo remain future work.
Invalid or inaccessible destinations show a warning and preserve the last valid
location and history. If a drive disconnects after loading, Refresh or navigating
back to it checks access again; continuous drive-disconnection notifications are
not implemented. Directory validation uses a worker and Qt loads listings
asynchronously. OS/network requests can still take time to finish.

## Quick Sort

1. Under Quick Sort in the sidebar (scroll down if necessary), choose **Add**.
   Enter a unique keyword, name, and an existing destination folder. Keywords are
   labels for now; there are no keyboard hooks. Optional colors/icons are not exposed yet.
   The selection hint explains whether clicking will open the destination or review a move.
2. Click a shortcut with no files selected to browse its destination. **Open**
   opens the highlighted destination even if files are selected.
3. In a source folder, use Ctrl/Shift or Ctrl+A to select files. Folder moves
   are not supported; deselect folders before using Quick Sort.
4. Click a shortcut to review the file list, sources, destination, total bytes,
   and conflicts. Choose Skip, Rename incoming, or Replace for each conflict.
   Existing conflicts default to Skip. Replace requires a separate confirmation.
5. Choose **Move files**. The progress dialog shows the current file/phase and
   copying progress for larger files. **Cancel after current file** finishes the
   current file safely and cancels remaining files; it does not undo completed moves.
6. Read the per-file results. **History** shows the latest 1,000 item records,
   UTC timestamps, and the database location. Edit/Delete/↑/↓ manage highlighted
   shortcuts. Deleting a shortcut never deletes the destination or its files.

Shortcuts and operation history live in `filespace.sqlite3` under Qt's
`AppLocalDataLocation` (normally `%LOCALAPPDATA%\FileSpace`), outside the repository.
No user-file content is stored in SQLite. Schema version 1 uses separate batch
and per-file tables. Connections are short-lived and local to their calling thread.
A database error prevents starting new transfers; a journaling failure during a
batch stops subsequent files and asks you to inspect the source/destination.

### Transfer safety and current limits

All moves, including same-drive moves, copy to a unique destination-side staging
file, flush it, verify SHA-256 content against the original, then publish without
overwriting an unexpected file. The published copy and unchanged source are
checked again before source removal. Named NTFS data streams, including the
`Zone.Identifier` attached to many downloaded files, are copied and SHA-256
verified too; the confirmation total includes their byte sizes. If the destination
cannot preserve a stream, the move fails and retains the original and its metadata.
This conservative approach is slower and
needs space for the full copy, but gives cross-drive and same-drive moves the
same tested transfer path. Names and sizes are revalidated after confirmation.
Renaming preserves the extension. There is no automatic move, deletion, or retry.

Explicit Replace keeps the prior destination in a uniquely named `.backup`
file until the transfer completes. Failed publication attempts restore the old
destination where possible. If final verification, source removal, or cleanup
fails, the result reports `needs_review` and any retained backup path. Inspect
both locations before retrying. Staging cleanup failures also report the path.

Protected Windows, application installation, application data, interpreter, and
FileSpace data/source directories are blocked as sources and destinations.
Symlinks, junctions, cloud reparse-point locations (including some OneDrive
folders), and encrypted/system files are rejected. Named data streams are preserved,
not stripped or executed. Timestamps/basic
mode metadata are copied; destination permissions follow the filesystem, and
full NTFS metadata/ACL migration is not implemented.

Navigation is disabled during Quick Sort tasks. Active previews are cleared and
the app waits asynchronously for an in-progress parser before starting a transfer.
Closing the app while a Quick Sort task is active is blocked until it finishes.
Unexpected process termination or power loss can leave `.partial`/`.backup`
files and `running`/`pending` journal entries. History is an audit aid, not an
automatic recovery or undo system. Recheck those files manually before retrying.
External programs can still change files; these checks reduce accidental races
but are not a transaction spanning the entire Windows filesystem.

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

Run automated browsing, preview, database, and transfer checks in temporary folders (standard-library unittest,
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

Quick Sort tests cover persistence after reopening the database, unique keywords,
UI add/edit/reorder/delete, no-selection navigation, cancelled confirmation,
multi-selection and completed moves, all conflict choices, replacement confirmation,
preview release, source/destination changes, new collision races, content verification
failure, simulated disk-full/locking/journal failures, protected paths, alternate
streams, cancellation, and per-file partial results. Every transfer fixture is
test-owned and temporary. Actual cross-volume hardware transfers, power loss,
removable-drive disconnection, and Windows ACL behavior require manual verification.
Start manual Quick Sort checks with disposable ordinary files and folders outside
the protected locations; verify shortcuts/history persist after restarting.

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
- `app/filesystem/safety.py`: protected-path, reparse-point, and unsupported-data checks.
- `app/filesystem/streams.py`: Windows named-stream enumeration and addressing.
- `app/filesystem/file_operations.py`: staged, verified file transfers and conflict rules.
- `app/services/quick_sort_service.py`: shortcut validation and journaled move coordination.
- `app/services/file_operation_service.py`: worker execution and cancellation requests.
- `app/database/`: SQLite connections, versioned schema, and repository operations.
- `app/ui/quick_sort_panel.py`: shortcut management and the confirmed move workflow.
- `app/ui/dialogs/quick_sort.py`: shortcut configuration and move/conflict confirmation.
- `tests/test_browsing.py`: disposable-folder browsing regression checks.
- `tests/test_previews.py`: generated-fixture preview and optional video checks.
- `tests/test_database.py`, `tests/test_file_operations.py`, `tests/test_quick_sort.py`:
  disposable-database, data-integrity, and full UI workflow checks.
- `docs/PRD.md`: product requirements.
- `requirements.txt`: pinned environment dependencies, including Qt support packages.
- Office extraction uses `python-docx`, `openpyxl`, and `python-pptx`; their
  supporting packages are also pinned in `requirements.txt`.
- `.gitignore`: excludes the local environment, caches, and build output.

Review changes before committing. Commits require approval; verify the intended
account and repository before any remote push.

Qt references: [PDF document rendering](https://doc.qt.io/qtforpython-6/PySide6/QtPdf/QPdfDocument.html)
and [image decoding limits](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QImageReader.html).
Transfer references: [Python filesystem operations](https://docs.python.org/3/library/os.html)
and [Qt application data locations](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QStandardPaths.html).
Windows stream references: [file streams](https://learn.microsoft.com/en-us/windows/win32/fileio/file-streams)
and [FindFirstStreamW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findfirststreamw).

# FileSpace

A local Windows desktop file manager built with Python and PySide6.
See [the PRD](docs/PRD.md) for the product requirements and milestones.

## Current scope

Milestone 6 adds internal and external file drag-and-drop, with confirmed copy/move transfers, to **FileSpace**, initially
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
model remains read-only; confirmed Quick Sort clicks and accepted file drops
use a separate transfer service. Search, general file commands, and undo remain future work.
Invalid or inaccessible destinations show a warning and preserve the last valid
location and history. If a drive disconnects after loading, Refresh or navigating
back to it checks access again; continuous drive-disconnection notifications are
not implemented. Directory validation uses a worker and Qt loads listings
asynchronously. OS/network requests can still take time to finish.

## Drag-and-drop

- Inside FileSpace, drag one or multiple selected files onto a folder row or a
  Quick Sort destination. Default: **Move**. Hold **Ctrl** when dropping to **Copy**.
- From Windows File Explorer, drop local files onto a folder row, an existing
  Quick Sort destination, or empty space in the file list (the current folder).
  The import dialog defaults to **Copy**, including for Quick Sort targets.
  Choose **Move** explicitly if wanted, then review the confirmation.
- Every drop still requires confirmation showing copy/move intent, selected
  files, sources, destination, total bytes (including named streams), and conflicts.
  Skip/Rename/explicit Replace, progress, cancellation between files, preview
  release, and per-file history use the same verified engine as Quick Sort clicks.
- Blue highlighting indicates a candidate target; red highlighting/no-drop cursor
  indicates an invalid target. Filesystem access, protected aliases, and availability
  are fully checked in the background after dropping, before confirmation.
- Dropping onto a file row, a blank shortcut area, a protected path, or the same
  source folder is rejected. Directory transfers, web/text/virtual-file drops,
  and dragging files out of FileSpace are not supported. Mixed file/folder input
  is rejected before any transfer. Busy transfer views do not accept new drops.

Windows receives a Copy acknowledgement for incoming drops so Explorer cannot
remove an original while a confirmation or worker is pending. FileSpace performs
an explicitly chosen external Move itself after verification. Sources that offer
only a native Move action are rejected; use a normal Explorer drag and choose
Move in the import dialog. Internal drags use a private in-process MIME payload
and cannot trigger an unconfirmed shell transfer outside FileSpace.

## Quick Sort

1. Under Quick Sort in the sidebar (scroll down if necessary), choose **Add**.
   Enter a unique keyword, name, and an existing destination folder. Keywords are
   labels, with keyboard activation for single A–Z letters while the file list
   has focus. Optional colors/icons are not exposed yet.
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

Keyboard enhancement (explicitly approved ahead of the PRD's original schedule):
focus the file list and press a configured single-letter keyword such as **F**.
It runs the same action as clicking the shortcut: review a confirmed move for
selected files, or navigate when nothing is selected. Matching is case-insensitive;
Shift+letter also works. Unassigned letters retain filename navigation. Multi-letter
keywords remain mouse-only labels. Ctrl/Alt commands, address/search entry, and
dialogs are unaffected. Held-key repeats and activations during a busy transfer
are ignored. No global keyboard hooks or system-wide bindings are installed.

Shortcuts and operation history live in `filespace.sqlite3` under Qt's
`AppLocalDataLocation` (normally `%LOCALAPPDATA%\FileSpace`), outside the repository.
No user-file content is stored in SQLite. Schema version 1 uses separate batch
and per-file tables. Connections are short-lived and local to their calling thread.
History distinguishes `copy` and `move`, including records created before
Milestone 6; no schema migration is required for the new operation type.
A database error prevents starting new transfers; a journaling failure during a
batch stops subsequent files and asks you to inspect the source/destination.

### Transfer safety and current limits

All copies and moves, including same-drive moves, copy to a unique destination-side staging
file, flush it, verify SHA-256 content against the original, then publish without
overwriting an unexpected file. The published copy and unchanged source are
checked again before reporting success. Copy retains the original; Move removes
it only after successful verification. Named NTFS data streams, including the
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

Drag-and-drop checks send Qt viewport events and test internal source detection,
Ctrl-copy, external Copy acknowledgement, folder/blank-space/shortcut targeting,
invalid targets/payloads, disabled views, deferred confirmation, and preserved
originals. End-to-end worker tests cover external Copy/explicit Move, internal
copy/move, import/confirmation cancellation, and history. Copy tests also cover
conflicts, verification failure, cancellation, and named-stream preservation.

Manual Milestone 6 verification (use disposable files):

1. Drag files within FileSpace onto a folder; confirm Move and check both locations.
2. Repeat holding Ctrl at drop time; confirm Copy and verify originals remain.
3. Drag files onto a Quick Sort destination; test both internal modes.
4. Drag from Windows File Explorer onto the current folder's blank area, a folder
   row, and a Quick Sort destination. Confirm Copy is initially selected; test
   explicit Move separately. Check Windows Explorer's source after each operation.
5. Cancel at each confirmation stage and check that nothing transferred. Check
   file-row/protected/same-folder drops, conflicts, and cancellation between files.
6. Test a cross-drive transfer and a file containing download-zone metadata.

Synthetic Qt events do not validate native Explorer/OLE interoperation. Physical
mouse drags from Windows Explorer and cross-volume hardware behavior still need
the manual checks above. Folder transfers remain outside the current scope.

Bulk-selection regression checks repeat transfers in the same window, including
Ctrl-click and Shift-click image batches after the listing refreshes. Selection
snapshots include every distinct file with selected cells, not just rows whose
every column is selected, so partially selected rows are not omitted from
confirmation or internal drags.

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
- `app/ui/drag_drop.py`: private internal drag payloads, URL import, and drop feedback/routing.
- `tests/test_browsing.py`: disposable-folder browsing regression checks.
- `tests/test_previews.py`: generated-fixture preview and optional video checks.
- `tests/test_database.py`, `tests/test_file_operations.py`, `tests/test_quick_sort.py`:
  disposable-database, data-integrity, and full UI workflow checks.
- `tests/test_drag_drop.py`: Qt drag/drop events and copy/move import workflows.
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
Drag/drop reference: [Qt drag-and-drop actions and source handling](https://doc.qt.io/qtforpython-6/overviews/qtgui-dnd.html).

# FileSpace

A local Windows desktop file manager built with Python and PySide6.
See [the PRD](docs/PRD.md) for the product requirements and milestones.

## Current scope

Milestone 3 provides read-only drive and folder browsing in a window titled **FileSpace**, initially
1200 × 800 logical pixels, with a navigation bar, scrollable sidebar, empty
file details view, and preview placeholder. Drag the dividers to resize panels.
Select a sidebar folder or drive to browse it. The Preview button hides
and restores the preview panel, preserving its previous proportions.

Back, Forward, Up, Refresh, and address entry work. Double-click folders to open
them; double-clicking files does not launch an external application. Relative
paths are interpreted against the current folder. Refresh reloads the listing
and available drives. Standard folders use Windows/Qt locations, including
redirected folders. Hidden/system entries follow Qt's default visibility.

The listing displays name, type, size, and modification date. It reads directory
metadata only; it does not preview file contents or modify user files. Search,
previews, Quick Sort, storage, and file operations belong to later milestones.
Invalid or inaccessible destinations show a warning and preserve the last valid
location and history. If a drive disconnects after loading, Refresh or navigating
back to it checks access again; continuous drive-disconnection notifications are
not implemented. Directory validation uses a worker and Qt loads listings
asynchronously. OS/network requests can still take time to finish.

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

Run automated browsing checks in temporary folders (standard-library unittest,
no additional test package required):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

These checks cover history, invalid/permission-denied paths, relative paths,
root navigation, stale navigation results, listing refresh, and read-only UI
settings. Real removable-drive disconnection and Windows ACL behavior still
require manual checks; permission denial is simulated in the automated check.
Module imports establish availability, not PDF rendering or codec playback;
those features will be tested in Milestone 4.

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
- `app/ui/preview_panel.py`: preview empty state.
- `app/services/file_browser_service.py`: worker validation and navigation history.
- `app/services/drive_service.py`: Qt standard folders and mounted volumes.
- `app/filesystem/path_validator.py`: read-only path/access validation.
- `tests/test_browsing.py`: disposable-folder browsing regression checks.
- `docs/PRD.md`: product requirements.
- `requirements.txt`: pinned environment dependencies, including Qt support packages.
- `.gitignore`: excludes the local environment, caches, and build output.

Review changes before committing. Commits require approval; verify the intended
account and repository before any remote push.

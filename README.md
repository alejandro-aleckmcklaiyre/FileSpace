# FileSpace

A local Windows desktop file manager built with Python and PySide6.
See [the PRD](docs/PRD.md) for the product requirements and milestones.

## Current scope

Milestone 2 provides a resizable window titled **FileSpace**, initially
1200 × 800 logical pixels, with a navigation bar, scrollable sidebar, empty
file details view, and preview placeholder. Drag the dividers to resize panels.
Select a sidebar location to update its display label. The Preview button hides
and restores the preview panel, preserving its previous proportions.

Navigation buttons, path entry, and search are not connected to filesystem
functionality yet. File browsing, previews, Quick Sort, storage, and file operations belong to later milestones.
The application does not read, move, copy, or delete user files.

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
- `app/ui/file_explorer.py`: empty details view and selected-location label.
- `app/ui/preview_panel.py`: preview empty state.
- `docs/PRD.md`: product requirements.
- `requirements.txt`: pinned environment dependencies, including Qt support packages.
- `.gitignore`: excludes the local environment, caches, and build output.

Review changes before committing. Commits require approval; verify the intended
account and repository before any remote push.

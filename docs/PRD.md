# FileSpace — Product Requirements & Technical Development Plan

**Project:** FileSpace  
**Product type:** Windows Desktop Application  
**Version:** 1.0 MVP  
**Status:** Planning / Pre-development  
**Development environment:** VS Code + OpenAI Codex  
**Primary language:** Python  
**GUI framework:** PySide6  
**Database:** SQLite  
**Operating system:** Windows 10/11

---

# PART 1 — PRODUCT REQUIREMENTS DOCUMENT (PRD)

## 1. Product Overview

### 1.1 Product Vision

FileSpace is a desktop file management application designed to make browsing, previewing, and organizing files easier.

It combines the familiar experience of Windows File Explorer with an integrated file preview panel and customizable Quick Sort shortcuts.

The application allows users to:

- Browse multiple storage drives.
- Navigate folders and files.
- Preview files without opening separate applications.
- Select and organize multiple files.
- Create custom destination shortcuts.
- Move files using drag-and-drop.
- Import files directly from Windows File Explorer.

### 1.2 Problem Statement

Traditional file management requires users to repeatedly open files to inspect their contents, navigate through multiple folders to find destinations, and manually move files one at a time.

This becomes inconvenient when managing large numbers of images, videos, documents, and other files.

FileSpace addresses these problems through:

1. An integrated preview panel.
2. Customizable destination shortcuts.
3. Multi-file organization.
4. Internal and external drag-and-drop functionality.
5. A unified interface for multiple drives.

### 1.3 Target User

The initial target user is an individual Windows PC user who:

- Works with different file types.
- Manages files across multiple drives.
- Frequently organizes images, videos, and documents.
- Wants faster file organization.
- Prefers a clean and customizable interface.

### 1.4 Core Product Principles

1. **Preview before opening:** Users should understand what a file contains without launching another application whenever possible.
2. **Organize with fewer clicks:** Frequently used destinations should be accessible through shortcuts.
3. **User-controlled operations:** Never automatically move or delete files without user authorization.
4. **Familiar navigation:** Preserve familiar file manager interactions.
5. **Local-first:** File information and operations should remain on the user's computer.
6. **Safe file handling:** Prevent accidental overwrites, unintended deletion, and unsafe operations.

---

# PART 2 — FUNCTIONAL REQUIREMENTS

## 2. Main Application Layout

The application should have four primary interface sections.

### 2.1 Left Sidebar — Navigation Panel

Purpose: Provide access to drives, folders, and Quick Sort shortcuts.

Required elements:

- Home
- Desktop
- Documents
- Downloads
- Pictures
- Videos
- Available storage drives
- Favorite folders
- Quick Sort shortcuts

Expected behavior:

- Clicking a drive opens its root directory.
- Clicking a folder navigates to that folder.
- Clicking a Quick Sort shortcut opens its configured destination when no files are selected.
- Users can add and remove favorite folders.
- The sidebar should support scrolling.

### 2.2 Center Panel — File Explorer

Purpose: Display files and folders from the currently selected location.

Required functionality:

- Display files and folders.
- Navigate between directories.
- Open folders.
- Select individual files.
- Multi-select files using Ctrl and Shift.
- Sort by name, size, type, and modification date.
- Search within the current location.
- Refresh the displayed contents.
- Support file drag-and-drop.
- Support context menus.

View modes:

- Details view
- Grid/icon view

Default view: Details.

Suggested columns:

| Column | Description |
|---|---|
| Name | File or folder name |
| Type | Extension or folder |
| Size | File size |
| Date Modified | Last modification timestamp |

### 2.3 Right Panel — File Preview

Purpose: Display the contents of a selected file without opening an external application.

Required behavior:

- Update preview when the selected file changes.
- Display file metadata.
- Support a preview panel toggle.
- Display a helpful message for unsupported formats.
- Show a loading indicator for large files.
- Handle corrupted or inaccessible files gracefully.

Supported preview types:

| File format | Preview behavior |
|---|---|
| JPG, JPEG, PNG, WEBP, BMP | Image preview |
| GIF | Image preview |
| PDF | Embedded PDF viewer |
| MP4, MKV, MOV, AVI | Video preview, subject to available codecs |
| TXT, LOG, CSV | Text preview |
| DOCX | Basic extracted text preview |
| XLSX | Spreadsheet data preview |
| PPTX | Extracted slide text preview |

Additional metadata:

- File name
- File extension
- File size
- Date modified
- File location
- Image dimensions, when applicable
- Video duration, when available

Technical note: Office document previews in the MVP may be simplified content previews rather than pixel-perfect Office rendering. Full-fidelity Office rendering can be considered for a later version.

### 2.4 Top Navigation Bar

Required elements:

- Back
- Forward
- Up one directory
- Refresh
- Address/path bar
- Search field
- Preview toggle

The address bar should support direct path entry.

Example:

`D:\Personal\Pictures`

Users should be able to navigate directly to a valid directory.

---

# 3. Quick Sort System

**Priority: Critical — Signature Feature**

Quick Sort is the application's main productivity feature.

It allows users to configure destination shortcuts and move selected files into those destinations.

### 3.1 Shortcut Configuration

Each shortcut must contain:

| Property | Description |
|---|---|
| Shortcut ID | Unique identifier |
| Keyword | User-defined shortcut, e.g. A |
| Shortcut Name | Example: Images |
| Destination Path | Example: D:\Personal\Images |
| Icon | Optional |
| Color | Optional |
| Created Date | Configuration timestamp |

Example:

| Keyword | Name | Destination |
|---|---|---|
| A | Images | D:\Personal\Images |
| B | Documents | D:\Personal\Documents |
| C | Videos | D:\Media\Videos |
| D | Work | D:\Work\Projects |

### 3.2 Quick Sort Workflow

1. User opens a source directory.
2. User selects one or multiple files.
3. User clicks a Quick Sort shortcut.
4. Application displays the intended destination.
5. User confirms the operation.
6. Application moves the selected files.
7. Application reports successful and failed operations.

### 3.3 Shortcut Behavior

When files are selected:

- Clicking a shortcut initiates the move workflow.

When no files are selected:

- Clicking a shortcut navigates to its destination.

### 3.4 Shortcut Management

Users should be able to:

- Create shortcuts.
- Edit shortcut names.
- Change keywords.
- Change destination paths.
- Delete shortcuts.
- Reorder shortcuts.
- Open destination folders.
- Validate whether a destination exists.

### 3.5 Keyboard Shortcuts

Future enhancement:

- A–Z custom shortcut assignments.
- Configurable key combinations.
- Keyboard-triggered Quick Sort operations.

For MVP, clicking shortcuts is sufficient. Avoid global keyboard hooks.

---

# 4. Drag-and-Drop System

**Priority: Critical**

The application must support two types of drag-and-drop operations.

### 4.1 Internal Drag-and-Drop

Users can drag files from the main file explorer into:

- Another folder.
- A destination folder.
- A Quick Sort shortcut.

Expected behavior:

- Dragging into a folder moves the file.
- Dropping onto a Quick Sort shortcut moves the file to its destination.
- Multiple files can be dragged together.
- Show visual indicators for valid drop targets.

### 4.2 External Drag-and-Drop

Users can drag files from Windows File Explorer into FileSpace.

Examples:

- Drag an image from the desktop into a destination folder.
- Drag multiple documents from Downloads into FileSpace.
- Drop files directly onto a Quick Sort shortcut.

The application must correctly distinguish between:

- Files originating inside FileSpace.
- Files originating outside FileSpace.

For external files, the user should be able to choose whether to copy or move them.

### 4.3 File Operation Rules

| Operation | Expected behavior |
|---|---|
| Drag into another folder | Move |
| Ctrl + drag | Copy |
| External drag | Copy by default, with an option to move |
| Drag onto Quick Sort | Move to configured destination |

Cross-drive moves should be handled safely, including progress reporting.

---

# 5. File Management Features

### 5.1 Multi-selection

- Select individual files.
- Select multiple files using Ctrl.
- Select ranges using Shift.
- Select all files using Ctrl + A.

### 5.2 Context Menu

Right-clicking a file should provide:

- Preview
- Open
- Open containing folder
- Copy
- Cut
- Paste
- Rename
- Delete
- Properties
- Move to Quick Sort destination

### 5.3 Search and Filters

MVP search functionality:

- Search by filename.
- Filter by file extension.
- Filter by file category.
- Sort by modification date.
- Sort by file size.

Search should initially be limited to the current directory and its subdirectories only when explicitly requested.

### 5.4 File Operation History

Record:

- Operation type.
- Source path.
- Destination path.
- Operation date.
- Operation result.
- Associated file names.

The history will support a future undo feature.

---

# PART 3 — TECHNICAL ARCHITECTURE

## 6. Recommended Technology Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Programming language | Python 3.12+ | Application logic |
| Desktop framework | PySide6 | Windows desktop UI |
| File operations | pathlib, shutil | File management |
| File browsing | QFileSystemModel | Filesystem navigation |
| Database | SQLite | Settings and operation history |
| Configuration | QSettings | Application preferences |
| Image preview | Qt image support | Image rendering |
| PDF preview | QtPdf / QtPdfWidgets | PDF rendering |
| Video preview | QtMultimedia | Video playback |
| Office previews | python-docx, openpyxl, python-pptx | Content extraction |
| Testing | pytest | Automated testing |
| Code quality | Ruff | Linting and formatting |
| Packaging | PyInstaller | Windows executable |

Use PySide6 modules according to their availability in the installed environment. Confirm PDF and multimedia support during the setup milestone.

## 7. Architecture Overview

Use a modular, layered architecture.

The application should separate:

1. Presentation layer.
2. Application/service layer.
3. Filesystem layer.
4. Data persistence layer.

### 7.1 Presentation Layer

Responsible for the visual interface.

Components:

- MainWindow
- SidebarWidget
- FileExplorerWidget
- PreviewPanel
- QuickSortPanel
- DriveSelector
- SearchWidget
- OperationProgressDialog

### 7.2 Application/Service Layer

Responsible for coordinating user actions.

Services:

- FileBrowserService
- FilePreviewService
- QuickSortService
- FileOperationService
- DriveService
- SearchService
- HistoryService

### 7.3 Filesystem Layer

Responsible for interacting with Windows files and directories.

Responsibilities:

- Reading file metadata.
- Enumerating directories.
- Moving files.
- Copying files.
- Renaming files.
- Deleting files when explicitly authorized.
- Validating destination paths.
- Handling permission errors.

### 7.4 Data Persistence Layer

SQLite database for:

- Quick Sort shortcuts.
- Favorite locations.
- Operation history.
- Application preferences, where appropriate.

The actual user files must remain in their existing filesystem locations. The database should store references and metadata, not duplicate the files.

## 8. Proposed Data Model

### Table: quick_sort_shortcuts

| Field | Type |
|---|---|
| id | INTEGER PRIMARY KEY |
| keyword | TEXT UNIQUE |
| name | TEXT |
| destination_path | TEXT |
| icon | TEXT |
| color | TEXT |
| created_at | DATETIME |

### Table: favorites

| Field | Type |
|---|---|
| id | INTEGER PRIMARY KEY |
| name | TEXT |
| folder_path | TEXT |
| created_at | DATETIME |

### Table: operation_history

| Field | Type |
|---|---|
| id | INTEGER PRIMARY KEY |
| operation_type | TEXT |
| source_path | TEXT |
| destination_path | TEXT |
| status | TEXT |
| created_at | DATETIME |

For multi-file operations, use a separate operation-items table in the final schema so that every file can be tracked independently.

Include database schema versioning to support future migrations.

---

# PART 4 — PROPOSED PROJECT STRUCTURE

## 9. Folder Structure

```text
FileSpace/
│
├── app/
│   ├── main.py
│   │
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── sidebar.py
│   │   ├── file_explorer.py
│   │   ├── preview_panel.py
│   │   ├── quick_sort_panel.py
│   │   ├── drive_selector.py
│   │   └── dialogs/
│   │
│   ├── services/
│   │   ├── file_browser_service.py
│   │   ├── file_preview_service.py
│   │   ├── quick_sort_service.py
│   │   ├── file_operation_service.py
│   │   ├── drive_service.py
│   │   ├── search_service.py
│   │   └── history_service.py
│   │
│   ├── filesystem/
│   │   ├── path_validator.py
│   │   ├── file_reader.py
│   │   └── file_operations.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── migrations.py
│   │
│   ├── models/
│   │   ├── file_item.py
│   │   └── shortcut.py
│   │
│   ├── utils/
│   │   ├── file_helpers.py
│   │   └── constants.py
│   │
│   └── resources/
│       ├── icons/
│       └── styles/
│
├── tests/
│   ├── test_file_operations.py
│   ├── test_quick_sort.py
│   ├── test_path_validation.py
│   ├── test_database.py
│   └── test_preview.py
│
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   └── DEVELOPMENT_PLAN.md
│
├── .gitignore
├── requirements.txt
├── README.md
└── main.py
```

The architecture may evolve as development progresses, but modules should remain separated by responsibility.

---

# PART 5 — MVP SCOPE

## 10. Version 1.0 Features

### Must Have

- [ ] Desktop application window.
- [ ] Left navigation sidebar.
- [ ] Drive selection.
- [ ] Directory navigation.
- [ ] File and folder listing.
- [ ] Details and grid views.
- [ ] Right-side preview panel.
- [ ] Image preview.
- [ ] PDF preview.
- [ ] Video preview.
- [ ] Text preview.
- [ ] Basic Office document previews.
- [ ] File metadata.
- [ ] Single and multi-file selection.
- [ ] Custom Quick Sort shortcuts.
- [ ] Manual destination configuration.
- [ ] Internal drag-and-drop.
- [ ] External drag-and-drop.
- [ ] File copy and move operations.
- [ ] Destination validation.
- [ ] File conflict handling.
- [ ] Basic operation history.
- [ ] Search and sorting.

### Later Versions

- Automatic file categorization.
- Advanced storage analytics.
- Duplicate file detection.
- Advanced cleanup assistant.
- Advanced file tagging.
- Cloud storage integrations.
- File synchronization.
- Advanced undo and recovery.
- Global keyboard shortcuts.
- Custom themes.
- Full-fidelity Office document previews.

## 11. Out of Scope for MVP

To keep the first version manageable, do not implement:

- Automatic deletion.
- Background file cleanup.
- Automatic file sorting.
- Cloud synchronization.
- User authentication.
- Multi-user access.
- Remote storage management.

---

# PART 6 — SAFETY AND RELIABILITY REQUIREMENTS

## 12. File Operation Safety

This is particularly important because the application will have access to real user files.

### 12.1 Confirmation

Before executing a bulk operation, display:

- Number of selected files.
- Source location.
- Destination location.
- Total file size.
- Potential conflicts.

### 12.2 File Conflicts

If a destination already contains a file with the same name:

Offer:

- Skip.
- Rename the incoming file.
- Replace, with explicit confirmation.

Never overwrite files silently.

### 12.3 Protected Locations

Prevent accidental destructive operations involving critical Windows directories, including Windows system directories and protected application locations.

Apply additional safeguards to:

- System folders.
- Application installation directories.
- Application data directories.
- The application's own database and configuration files.

The application should not request administrator privileges by default.

### 12.4 Large File Operations

For large operations:

- Show progress.
- Show the current file being processed.
- Allow cancellation where safe.
- Handle permission errors.
- Report partial failures.
- Avoid freezing the interface.

Filesystem operations must run outside the main GUI thread using an appropriate Qt worker/thread mechanism.

### 12.5 Data Integrity

- Validate source and destination paths.
- Prevent moving a folder into itself or its descendants.
- Handle unavailable drives.
- Detect invalid paths.
- Preserve file extensions during renaming.
- Never assume a move succeeded until verified.

For cross-drive moves, copy and verify before removing the original. If verification fails, preserve the original.

---

# PART 7 — CODEX IMPLEMENTATION PLAN

## 13. Development Strategy

Use milestone-based development.

Codex must not implement the entire application in one request.

For every milestone:

1. Review requirements.
2. Propose a technical implementation plan.
3. Explain files that will be created or modified.
4. Wait for approval.
5. Implement the approved changes.
6. Run relevant tests.
7. Explain the result.
8. Review Git changes.
9. Commit only after approval.

## 14. Milestone Breakdown

### Milestone 1 — Development Environment and Application Foundation

Deliverables:

- Python virtual environment.
- PySide6 installation.
- Initial project structure.
- Application entry point.
- Basic desktop window.
- Application title and dimensions.
- Git repository initialization.
- Initial README.

Acceptance criteria:

- Application launches successfully.
- Main window renders.
- No import errors.
- Dependencies are documented.
- Git repository is initialized.

### Milestone 2 — Main UI and Navigation

Deliverables:

- Main application layout.
- Left sidebar.
- Center file explorer.
- Right preview placeholder.
- Top navigation bar.
- Basic styling.

Acceptance criteria:

- Application displays the three main panels.
- Panels have appropriate proportions.
- Navigation elements respond to interaction.
- Layout resizes correctly.

### Milestone 3 — Drive and File Browsing

Deliverables:

- Available drive detection.
- Drive selector.
- Folder navigation.
- File listing.
- File metadata.
- Address bar.
- Back and forward navigation.

Acceptance criteria:

- Users can select available drives.
- Users can browse directories.
- Files and folders are displayed correctly.
- Invalid or unavailable paths are handled gracefully.

### Milestone 4 — Preview Engine

Deliverables:

- Image preview.
- PDF preview.
- Video preview.
- Text preview.
- Basic DOCX, XLSX, and PPTX previews.
- File metadata panel.

Acceptance criteria:

- Selecting a supported file updates the preview.
- Unsupported formats display a fallback message.
- Preview errors do not crash the application.
- Large previews do not freeze the UI.

### Milestone 5 — Quick Sort

Deliverables:

- Shortcut management.
- Create/edit/delete shortcuts.
- Destination selection.
- Multi-file selection.
- Move confirmation dialog.
- Conflict handling.
- Operation history.

Acceptance criteria:

- Users can create custom shortcuts.
- Shortcuts persist after restarting the application.
- Selected files can be moved to configured destinations.
- Empty-selection shortcut clicks navigate to destinations.
- Invalid destinations are rejected.

### Milestone 6 — Drag-and-Drop

Deliverables:

- Internal file dragging.
- Internal folder dropping.
- Quick Sort drag targets.
- External file dropping.
- Copy/move behavior.
- Progress dialog.

Acceptance criteria:

- Files can be moved between folders.
- Multiple files can be transferred.
- External files can be imported.
- Cross-drive transfers work safely.
- Invalid drop targets are rejected.

### Milestone 7 — Search, Filters, and Quality Improvements

Deliverables:

- Filename search.
- File type filters.
- Sorting.
- Details and grid views.
- Context menus.
- Favorites.
- Improved error handling.

Acceptance criteria:

- Search returns relevant results.
- Filters work correctly.
- Context menu actions work.
- Navigation remains responsive.

### Milestone 8 — Testing and Windows Packaging

Deliverables:

- Automated tests.
- Manual acceptance testing.
- Error handling review.
- Windows executable.
- Application icon.
- Installation and usage documentation.

Acceptance criteria:

- Application launches outside VS Code.
- Dependencies are bundled or documented.
- Core file operations pass testing.
- No critical data integrity issues remain.

---

# PART 8 — CODEX DEVELOPMENT RULES

## 15. Instructions for Codex

Codex should follow these rules throughout the project.

1. Read the PRD and architecture documents before implementation.
2. Do not change the approved architecture without explaining why.
3. Do not introduce unnecessary dependencies.
4. Use modular, readable Python code.
5. Keep UI code separate from filesystem operations.
6. Use type hints where practical.
7. Handle filesystem exceptions explicitly.
8. Do not use hardcoded personal directory paths.
9. Never execute destructive file operations without user confirmation.
10. Never silently overwrite files.
11. Write tests for important file operations.
12. Explain commands before asking the developer to run them.
13. Do not install packages or execute destructive commands without approval.
14. Do not create unrelated features.
15. Report incomplete functionality honestly.
16. Preserve existing working functionality when implementing new features.

## 16. Git Workflow

Use the following development approach:

- `main`: Stable application version.
- `develop`: Integration branch, when needed.
- `feature/...`: Individual development features.

Suggested feature branches:

```text
feature/main-ui
feature/file-browser
feature/preview-engine
feature/quick-sort
feature/drag-drop
feature/search
```

Commit messages should describe actual changes.

Examples:

```text
feat: create main application window
feat: implement drive navigation
feat: add image preview support
feat: implement quick sort shortcuts
fix: handle duplicate filename conflicts
test: add file operation tests
```

Do not push to a remote repository until the correct GitHub account and repository have been verified.

---

# PART 9 — DEFINITION OF DONE

## 17. MVP Completion Criteria

FileSpace Version 1.0 is considered complete when a user can:

1. Launch the desktop application.
2. Select a storage drive.
3. Browse its folders and files.
4. Select a file and preview it on the right panel.
5. Preview supported images, PDFs, videos, text, and basic Office documents.
6. Select multiple files.
7. Create a custom Quick Sort shortcut.
8. Move selected files using that shortcut.
9. Drag files between folders.
10. Drag files from Windows File Explorer into the application.
11. Handle filename conflicts safely.
12. Review completed file operations.
13. Close and reopen the application without losing shortcut configurations.

**Final product goal:** A reliable, responsive, local Windows file manager that makes file organization faster and more convenient than repeatedly navigating through Windows File Explorer.

---

# PART 10 — FIRST CODEX INSTRUCTION

Use this as the first instruction after placing the PRD and architecture documents inside the project's `docs/` folder.

**Do not ask Codex to build the whole application yet.**

Initial prompt:

> We are starting development of FileSpace, a Windows desktop file manager built with Python and PySide6.
>
> I have provided the Product Requirements Document and technical architecture in the docs directory.
>
> Your first responsibility is to review these documents and understand the application's intended behavior, technical architecture, MVP scope, and safety requirements.
>
> We will follow milestone-based development.
>
> For now, focus exclusively on Milestone 1: Development Environment and Application Foundation.
>
> Before making any changes:
>
> 1. Summarize your understanding of the project.
> 2. Identify the technical dependencies required for Milestone 1.
> 3. Propose the initial project directory structure.
> 4. Explain the purpose of each proposed file and folder.
> 5. Provide the exact terminal commands needed, explaining what each command does before I execute it.
> 6. Identify potential setup issues on Windows.
> 7. Define how we will verify that Milestone 1 is successful.
>
> Do not implement future milestones.
>
> Do not install dependencies, modify files, or execute commands until I approve the proposed plan.
>
> Act as a senior software engineer guiding a developer who has basic programming experience. Explain important technical decisions clearly without overwhelming me with unnecessary theory.
>
> Our objective is to build a working, maintainable desktop application rather than generate a large amount of code without understanding it.

---

**END OF DOCUMENT**

*FileSpace — Product Requirements & Technical Development Plan, Version 1.0*
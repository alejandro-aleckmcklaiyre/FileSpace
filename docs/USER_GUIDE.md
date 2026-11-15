# FileSpace Windows preview

## Start

Extract the complete FileSpace folder to a writable location, then double-click
`FileSpace.exe`. Keep its `_internal` folder beside it. Python and VS Code are
not required to launch the package. Do not run it as administrator. This preview
is a folder distribution, not an installer, and is not digitally signed.

Use the development output at `dist\FileSpace\FileSpace.exe`, or extract the
Windows ZIP to a new folder first. Do not run an executable from inside the ZIP.

## Browse and preview

Choose a standard folder or drive on the left, double-click folders, or enter a
folder path. Back, Forward, Up and Refresh work like familiar file managers.
Select a file to preview it on the right. Preview toggles that panel. Images,
PDF pages, videos, text and basic Office content are supported within documented
size limits. Press Play for video. Double-clicking a file does not execute it;
right-click Open explicitly uses its Windows association.

Search matches names in the current folder only. Category and extension filters
combine with search. Use the sort and Details/Grid controls on the second row.
Grid uses filesystem icons, not image thumbnails. Clear filters to see all files.

Right-click Properties to see metadata. Under Favorites, Add current saves the
open folder, and Remove deletes only the saved favorite entry.

## Organize files

Add a Quick Sort destination with a unique keyword, name and existing directory.
Select files with Ctrl/Shift or Ctrl+A. Click a destination to review a move.
Single A–Z keywords also work when the file list has focus. With no selection,
the same shortcut opens the destination. Open always navigates without transferring.

Internal file drops move by default; Ctrl at drop time copies. External drops
from Explorer default to Copy, with Move explicitly selectable. Every transfer
still requires confirmation and resolves conflicts through Skip, Rename incoming,
or explicitly confirmed Replace. FileSpace verifies copies, including NTFS named
streams, before removing originals during a move. Cancel stops between files.

Copy/Cut only record clipboard intent. Paste confirms and performs the transfer.
Ctrl+C/X/V work in a focused file view. Rename/F2 preserves the extension and
refuses collisions. Delete confirms and sends files to the Recycle Bin; restore
them using Windows. There is no permanent-delete action or application undo.

Review per-file results and History after any partial failure. Never assume that
a failed batch means no file moved. Retained `.partial` or `.backup` paths are
reported when cleanup or a replacement could not finish.

## Your settings and history

The database is normally `%LOCALAPPDATA%\FileSpace\filespace.sqlite3`; the view
preference is `filespace.ini` beside it. History displays the exact database path.
The packaged and source applications share these settings when run as the same
Windows user. Do not run both against the same settings at once while validating
the preview. Schema 2 preserves earlier shortcuts/history and adds favorites.

Local diagnostic logs are in the same data folder under `logs\filespace.log`.
They rotate at 2 MiB, retaining two backups. Logs can contain paths and exception
messages; review them before sharing. They do not intentionally record file content.

## If something fails

- Preserve the source, destination, any reported backup, and the operation history.
- Read the per-file result; some files may have completed before an error.
- Check that a drive is available and another application is not locking the file.
- Confirm that the entire `_internal` folder was extracted alongside the executable.
- Check the local log for unexpected errors. If startup itself fails before logging
  starts, retain the Windows/PyInstaller error message.
- Do not delete configuration or database files as an initial troubleshooting step.

Folder mutations, links/junctions/cloud reparse-point moves, encrypted/system file
transfers, protected locations, and case-only renames remain excluded. See
`KNOWN_LIMITATIONS.md` and the manual acceptance checklist before relying on this
preview for important file organization.

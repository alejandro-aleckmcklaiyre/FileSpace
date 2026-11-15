# FileSpace 1.0.0-preview: manual acceptance findings (Windows)

Tested on the packaged build (FileSpace-1.0.0-preview-windows-x64.zip, extracted to D:\Pkg)
on 2026-11-15, using disposable files in D:\FS_TestLab. Drives: C: (NTFS), D: (NTFS),
E: (exFAT USB). Most test source files were Read-only (attrib shows R).

Release status: **BLOCKED** by Fix 1, Fix 5 and Fix 8 (data integrity / checklist
requirements), plus the untested no-Python machine check.

## Results

| # | Check | Result |
|---|---|---|
| 1 | Launch from Explorer, window and icon render | Pass |
| 2 | Clean Windows machine without Python | **Pending** (no second PC/VM available) |
| 3 | Navigation, bad path keeps last location | Pass |
| 4 | Search / extensions / sort | Pass |
| 5 | Details/Grid, Ctrl/Shift batches, hidden file excluded from confirmation | Pass |
| 6 | Preview types, rapid selection, hide/reopen | Pass |
| 7 | Video play/pause/seek/audio, media released | Pass |
| 8 | Shortcut/favorite/view mode persist after restart | Pass |
| 9 | Keyboard shortcuts vs typing fields, Ctrl+A | Pass |
| 10 | Drag and drop (internal, Ctrl-copy, from Explorer) | **Fail** (Fix 8) |
| 11 | Copy/Cut/Paste | Pass on non-read-only files; **Fail** on read-only source Move (Fix 1b) |
| 12 | Conflicts: Skip / Rename / Replace | Skip Pass; **Fail** Replace over read-only destination (Fix 1a) |
| 13 | Cross-drive transfer with download metadata | Pass on NTFS (D: to C:, Zone.Identifier kept); **Fail** to exFAT (Fix 5) |
| 14 | Locked file, unavailable destination | Pass (originals preserved, partial results reported). Unplug test not run |
| 15 | Cancel a multi-file transfer | Pass (UX note, Fix 6) |
| 16 | Protected locations, self-folder, junction target | Pass |
| 17 | Rename collision / cancel / extension kept | Pass |
| 18 | Recycle and restore | Pass |
| 19 | Open / Open containing folder | Pass with note (Fix 4) |
| 20 | Close/restart, local log | Pass with notes (Fix 7) |

## Fix 1 (BLOCKER, data integrity): Read-only files break cleanup

One root cause, several symptoms. The Read-only attribute is preserved on the copy
(expected), but cleanup steps fail with WinError 5 when the target is read-only.

1a. Replace over an existing read-only destination file
- Repro: src\ALEJANDRO (4).pdf into dest\ where a read-only ALEJANDRO (4).pdf exists, choose Replace.
- Result: new file written, SHA-256 matches, but the read-only .filespace-<id>.backup
  cannot be deleted (WinError 5). Status needs_review, .backup left behind.
  Reproduced twice (random.txt and the PDF).

1b. Move of a read-only source
- Repro: read-only movetest.pdf.pdf, Cut, Paste into dest.
- Result: copy verified (hashes match), but deleting the original fails (WinError 5).
  Status needs_review, original remains in src.

1c. A one-time .partial failure
- Copy of a 0 KB random.txt: rename of .filespace-<id>.partial to random.txt failed with
  WinError 32, then cleanup failed with WinError 5. Retrying later worked. Possibly a
  transient lock (antivirus or indexer) or an unclosed handle. Not confirmed.

Requested change:
- Add one helper (for example safe_remove / safe_replace) that clears the Read-only flag
  (os.chmod(path, stat.S_IWRITE) or SetFileAttributes) before every delete or rename of an
  original, backup or staging file, and use it everywhere.
- Restore the source's Read-only attribute on the final destination file after
  verification, so attributes are still preserved.
- Staging and backup files should not inherit Read-only in the first place.
- Add a short retry with backoff (about 5 tries over 1 second) for WinError 32 and 5 on
  rename/delete, and make sure all handles to the staging file are closed first.

## Fix 3: Result status and History reporting

- If the final file is copied and SHA-256 verified and only a cleanup step failed
  (backup, staging, or deleting the original on Move), don't report a vague needs_review.
  Use a clear status such as "copied, cleanup warning" (Move: "copied, original not
  removed") and list the leftover path in History.
- Reserve needs_review for cases where the final result could not be verified.
- Keep the existing good behavior: the original is retained when a Move can't finish.

## Fix 4 (minor): Open containing folder doesn't select the file

- It opens the correct folder but the file isn't highlighted.
- Use explorer /select,"<full path>" (or SHOpenFolderAndSelectItems), with the path quoted.

## Fix 5 (BLOCKER for removable drives): Copy to exFAT/FAT32 fails

- Copying any file from D: (NTFS) to E: (exFAT), including plain files with no streams
  (random.txt, plain1.txt), fails with:
  "[Errno 87] Cannot inspect file streams safely: 'E:\FS_Test\.filespace-<id>.partial'".
  The file is not created. The original is kept and no .partial is left behind (good).
- Likely cause: stream enumeration on the staging file returns an invalid-parameter
  error on filesystems without named streams, and it is treated as a hard failure.
- Requested change: check whether the destination volume supports named streams
  (GetVolumeInformation, FILE_NAMED_STREAMS). If it doesn't, skip stream inspection on
  the destination and only fail if the SOURCE actually has streams that can't be
  preserved. Plain files must copy normally to exFAT/FAT32.
- For a source with Zone.Identifier copied to exFAT, the current refusal ("Cannot
  preserve file metadata stream :Zone.Identifier:$DATA ... original kept") is
  acceptable. Add a clear "Copy without metadata" choice in the confirmation dialog.

## Fix 6 (UX, minor): Cancel feedback and dialog titles

- Cancel during a ~15 GB file waits for the current file (as specified), but the UI shows
  no progress and a dialog says "Quick Sort is active ... Cancel stops after the current
  file", and Exit is refused. Show "Cancelling after the current file..." with progress for
  the current file, keep the window responsive, and allow Exit with a warning that the
  staging file will be cleaned up.
- Dialog titles say "Quick Sort could not complete" / "Quick Sort is active" for plain
  Copy, Paste and Rename. Titles should match the action.

## Fix 7 (minor): Logging and missing-folder handling

- Transfer-level failures (WinError 5/32, Errno 87, Errno 13) are in History but not in
  the error log. Also log them with the path and error code.
- Expected rejections (Protected location, already in destination, invalid name, name
  exists) are logged as ERROR with full tracebacks. Use WARNING/INFO without a traceback.
- A deleted folder (for example a stale Favorite) raises an unhandled FileNotFoundError in
  file_operations.build_plan / safety.check. Show "Folder no longer exists" and offer to
  remove the Favorite.
- If the destination folder disappears before a transfer is confirmed, show
  "Destination folder no longer exists" instead of the raw WinError 2 text, and don't
  show a second "Cannot open folder" dialog. Go to the nearest existing parent instead.

## Fix 8 (BLOCKER per checklist): Drag and drop does not work

- Grid view: pressing and dragging on a file starts a rubber-band selection, not a drag.
- Details view: the drag starts, but every drop target tried (file list, folder rows,
  Favorites, Quick Sort entries, drives) shows the "not allowed" cursor.
- Dragging a file from Explorer into the window also shows "not allowed".
- FileSpace was not running elevated.
- Moving via Quick Sort (select a file, click a destination) works; that is not a drag.
- Expected: internal drag = move, Ctrl-drag = copy, external drop = copy by default, move
  only when explicit, with the normal confirmation dialog. Enable drag on both views
  (rubber band only on empty space), accept URL drops on valid targets
  (dragEnterEvent/dragMoveEvent/dropEvent), and honor Ctrl.

## Regression tests to add

- Replace over a read-only destination: no leftover .backup, no needs_review, correct
  content and hash.
- Move of a read-only source: the original is removed after verification and the
  destination keeps its attributes.
- Staging and backup cleanup when the file is read-only.
- Retry logic: simulate a transient PermissionError (WinError 32) on rename.
- Plain file copy to a non-stream filesystem succeeds; a file with Zone.Identifier is
  refused or offered a no-metadata option, and no partial is left.
- Zero-byte file copy and replace.
- Open containing folder builds a command with /select and a quoted path.
- Drag and drop: internal move, Ctrl copy, external copy default, in both views.

## Working correctly (don't change)

Skip conflict handling, SHA-256 verification on copies, retaining the original when a
Move can't finish, Zone.Identifier preservation on NTFS, partial-batch reporting,
locked-file handling, protected-location rejection (AppData, C:\Windows, self-folder,
junction), rename collision handling, cancel between files, Recycle and restore,
navigation, search/sort, preview, video, saved settings, keyboard handling.

## After fixing

- Rebuild the package and ZIP, then re-run the packaged smoke checks.
- Re-run on the packaged .exe: read-only Replace, read-only Move, copy to the exFAT USB
  (and the unplug-during-transfer test, which could not be run), drag and drop in both
  views, and the no-Python machine check.
- Update docs\ACCEPTANCE_TESTS.md and MILESTONE_8_REPORT.md.

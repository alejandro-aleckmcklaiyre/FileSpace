# Packaged Windows manual acceptance

**Release status: BLOCKED.** Owner testing on 2026-11-15 found read-only cleanup,
exFAT transfer, and drag/drop failures. See [original findings](../FileSpace_acceptance_findings.md)
and [next-step plan](ACCEPTANCE_REMEDIATION_PLAN.md). Results below apply to the
1.0.0-preview ZIP extracted to `D:\Pkg`, with disposable fixtures on NTFS C:/D:
and exFAT USB E:. The clean-machine and unplug tests remain pending.

Use copies of disposable files in folders outside FileSpace, AppData and Windows
system directories. Keep important originals elsewhere. Record Windows build,
machine, package hash, date, and pass/fail notes. Use the packaged executable for
these checks, not `python main.py`.

| Check | Expected result | Status |
|---|---|---|
| Extract complete ZIP elsewhere; double-click FileSpace.exe | Window/icon render outside VS Code with no activated venv | Pass |
| Repeat on a clean Windows 10/11 machine without Python | App launches using bundled components | Pending: no clean PC/VM available |
| Standard folders/drives/address/history/unavailable path | Correct navigation; failed path preserves last location | Pass |
| Search/extensions/categories/sort | Correct current-folder results and numeric sizes/dates | Pass |
| Details/Grid switching and repeated Ctrl/Shift batches | All selected files remain in confirmation; hidden files excluded | Pass |
| Supported preview types, rapid selection, hide/reopen | Correct preview or helpful error; UI stays usable | Pass |
| Video play/pause/seek/audio on your files | Playback works or codec error is clear; hiding releases media | Pass |
| Shortcut CRUD/reorder/favorite/view mode; restart | Saved configuration/history persist | Pass |
| Focused A–Z key; typing fields; Ctrl+A | Confirmation/navigation; text entry unaffected | Pass |
| Actual mouse drags inside app and from Explorer | Internal move/Ctrl-copy; external copy default/explicit move | FAIL: Fix 8 |
| Copy/Cut/Paste and cancelled confirmation | Originals retained until a confirmed verified move | Partial: read-only Move fails (Fix 1b) |
| Skip/Rename/explicit Replace; inspect History | Chosen conflict behavior and per-file outcomes | Partial: read-only Replace fails (Fix 1a) |
| Physical cross-drive transfer with download metadata | Verified content/streams preserved; move then removes original | NTFS pass; exFAT FAIL (Fix 5) |
| Locked file, unavailable destination, safe disconnect test | Original preserved on failure; partial results reported | Locked/unavailable pass; unplug pending |
| Cancel a multi-file transfer | Current file finishes safely; later files cancelled | Pass; feedback issue (Fix 6) |
| Protected locations/self-folder/link targets | Mutation rejected without changing files | Pass |
| Rename collision/cancel | No overwrite; extension retained | Pass |
| Recycle disposable file, then restore in Windows | File appears in Recycle Bin and can be restored | Pass |
| Explicit Open/Open containing folder | Correct Windows association/location; no DLL conflict | Pass; file selection missing (Fix 4) |
| Close/restart packaged app, check local log | Normal exit; readable local error diagnostics when needed | Pass; diagnostic issues (Fix 7) |

Source features were reviewed by the project owner during milestones 1–7; that
does not automatically mark this packaged checklist complete. Automated test and
smoke results are recorded separately in `MILESTONE_8_REPORT.md`. A failed critical
data-integrity check blocks release sign-off. Do not retry a partial move blindly;
retain logs/history and inspect source, destination, and any reported backup.

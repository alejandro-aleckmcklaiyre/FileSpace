# Preview.2 stabilization report

Date: 2026-11-15 (Asia/Manila). Version: `1.0.0-preview.2`, Windows x64.
Branch: `feature/windows-packaging`; this report accompanies the preview.2 stabilization commit.
Baseline: `fc5363a` (Milestone 8 preview snapshot).

## Implemented changes

- Read-only Move/Replace and owned staging/backup cleanup handle the Read-only bit
  explicitly, preserving other attributes and restoring the bit after failed removal.
  Source and backup identity/state are checked. Sharing violations have bounded
  retries; permanent permission denial is retained as a failure.
- Verified results distinguish original-not-removed, cleanup warning, completed Move
  with backup warning, and unverified publication. History includes recovery paths.
  A Move with completed source removal clears a matching Cut clipboard even when
  backup cleanup warns. Warnings keep the batch partial, not completed.
- Volume capability queries distinguish a filesystem without named streams from an
  inspection failure. Plain-file non-stream copies are covered by simulated capability
  regression; NTFS metadata preservation remains covered. Stream loss is refused.
- Grid drag flags are restored after Qt Static movement disabled them. Favorites,
  drives and standard locations are now drop targets. Confirmation and conservative
  external Copy acknowledgement remain in place. Native entry/drop diagnostics are
  written to the local app log.
- Missing Favorites offer removal; refreshing a deleted current folder recovers to
  an existing parent. A disappearing transfer destination produces a clear message
  without a second navigation warning in the regression scenario.
- Expected rejections log without traceback; per-file failures log paths and OS codes.
  Action titles identify Copy, Move, Rename, Open or recycling. Cancel keeps progress
  visible; requested exit waits for current-file verification and cleanup. Results
  remain in History when exiting without the normal results dialog.
- Open containing folder uses an Explorer selection request with separate arguments,
  without a command shell. Native highlighting remains a manual acceptance check.

## Verification

- Full source suite: **123 passed, plus 8 subtests**.
- Ruff passed; dependency consistency passed; Git whitespace check passed.
- Source GUI smoke: **12/12 passed** (`artifacts/source-preview2-smoke.json`).
- Frozen executable, unrelated working directory and sanitized environment:
  **12/12 passed** (`artifacts/packaged-preview2-smoke.json`).
- ZIP extracted elsewhere, same isolated launcher: **12/12 passed**
  (`artifacts/relocated-preview2-smoke.json`).
- Packaged checks now cover actual Windows read-only Replace/Move, preserved final
  attributes, no backup leftovers, and zero-byte copy/replace. Existing preview,
  video, transfer, history, persistence and bundle-isolation checks still pass.
- Qt regressions cover file-press/drag initiation in Details and Grid, URL events
  dispatched through both viewports, supported sidebar targets, missing folders,
  cancellation/exit coordination and expected-error logging.

Package: `dist/FileSpace/FileSpace.exe` (keep the entire FileSpace folder).
ZIP: `dist/FileSpace-1.0.0-preview.2-windows-x64.zip` (79,043,110 bytes).
SHA-256: `ba6196939ff06e0c92b89fc020e8d43bc9314999242f303a704c6c1f577b2d79`.
The original preview ZIP is retained separately. Build inventory is in ignored
`build/package-manifest.json`; raw reports are in ignored `artifacts/`.

## Remaining acceptance gates

**Release sign-off is still blocked pending owner retesting.** The initial
[owner findings](../FileSpace_acceptance_findings.md) are preserved unchanged.
The historical table in `ACCEPTANCE_TESTS.md` applies to the original `1.0.0-preview`; the new focused
preview.2 checklist is separate and all owner checks remain pending.

- The cause of the reported Details/Explorer native drop refusal is not established.
  Grid configuration and missing sidebar targets are corrected, but real Windows
  mouse/OLE behavior must be repeated before declaring Fix 8 resolved.
- Attempts at native mouse automation could not complete here: Windows denied
  SetCursorPos even outside the sandbox. No native OLE success is claimed. A temporary
  diagnostic harness was removed; it is not part of the application or package.
- Physical exFAT copy/move, NTFS stream refusal on exFAT, safe USB disconnect, clean
  Windows without Python, large-file cancellation, and native Explorer highlighting
  remain manual checks. Isolated launch is not proof of clean-machine acceptance.
- A metadata-stripping transfer mode was deliberately deferred. Do not silently
  discard Zone.Identifier or other streams. Transient zero-byte locks are covered
  by retries/regressions, but their original external cause is unconfirmed.

Follow the focused [acceptance checklist](ACCEPTANCE_TESTS.md). Use disposable
files, record the new version/hash, and retain history/logs on any failure.

## Implementation references

- [Qt QListView movement/view mode and drag flags](https://doc.qt.io/qt-6/qlistview.html).
- [Microsoft volume capability queries](https://learn.microsoft.com/en-us/windows/win32/fileio/obtaining-volume-information).

The owner authorized committing and pushing this stabilization snapshot. No
installer, release upload, signing or stable-branch merge is included. Release
sign-off remains pending the acceptance gates above. UI redesign remains separate.

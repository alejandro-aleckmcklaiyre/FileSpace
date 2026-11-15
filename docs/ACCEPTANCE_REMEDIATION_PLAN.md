# Acceptance remediation plan

Status: approved and implemented in `1.0.0-preview.2`; packaged owner retesting pending. Preserve the original
[findings](../FileSpace_acceptance_findings.md) as test evidence. Milestone 8 is a
packaging preview snapshot, not a signed-off MVP release. UI redesign follows
reliability corrections and packaged acceptance.

## 1. Transfer safety and filesystem compatibility

Address Fix 1, Fix 3, and Fix 5 together because they share the transfer lifecycle.

- Introduce narrowly scoped Windows attribute and cleanup helpers. Change only the
  read-only bit, preserve other attributes, and restore originals on unsuccessful
  operations. Revalidate identity/state before source deletion or replacement.
  Do not blanket-clear attributes on arbitrary user paths or bypass ACLs.
- Keep owned staging files writable until publication; preserve intended final
  attributes. Handle read-only backups and verified Move source removal explicitly.
  Rollback must retain the previous destination and its original attributes.
- Retry only identified transient sharing/lock failures with bounded backoff in
  the worker. Access denied may be an ACL or protection failure, so do not blindly
  retry every WinError 5. Never treat a lock as permission to overwrite.
- Track publication, verification, source removal, and backup cleanup separately.
  Show a verified copy with cleanup warning distinctly from an unverified result;
  list recovery paths in History. A Move whose source remains is not a completed Move.
- Detect volume named-stream capability. A plain file must copy to exFAT/FAT32;
  unknown capability or access failures must not be interpreted as no streams.
  Preserve and verify streams on NTFS. Continue refusing stream loss by default.
- Defer the optional Copy without metadata feature to an explicit scope decision:
  it changes the current preservation guarantee. If approved, make the loss clear
  before confirmation and record it in History; never silently strip metadata.

Exit checks: actual Windows read-only Move/Replace, read-only cleanup and rollback,
zero-byte copy/replace, simulated transient failures and permanent denials, verified
cleanup-warning history, plain exFAT copy, NTFS stream preservation, refusal for
unpreservable streams, no unexplained leftovers, original retained on failure.

## 2. Native drag/drop

Address Fix 8. Reproduce with the packaged executable and instrument event delivery,
model drag flags, viewport handling, and Grid gesture initiation before selecting
a fix. Existing synthetic handler tests do not prove real Windows OLE interaction.

Keep internal move/Ctrl-copy, external copy default, explicit external move,
protected-location checks, batch selection, and confirmation. Do not allow the shell
to delete a source independently of FileSpace's verified worker.

Exit checks: real mouse drags in Details and Grid, onto folder rows, Favorites and
Quick Sort targets, from Explorer, Ctrl-copy, cancellation, and invalid targets.
Add regression coverage at the gesture/event-dispatch layer where practical.

## 3. Diagnostics and usability

Address Fix 7, Fix 6, and Fix 4 after the transfer lifecycle is stable.

- Handle stale favorites and disappearing destinations without unhandled errors
  or duplicate dialogs; offer favorite removal and safe navigation recovery.
- Log per-file failures with operation, path and OS error code. Expected validation
  failures should not produce unexpected-error tracebacks.
- Use action-specific titles and show current-file progress and cancellation state.
  Retain safe cancellation between files. Do not force-kill an active worker when
  closing: warn, request cancellation, and exit only after verified work/cleanup
  completes. Immediate exit would require a separate interruption/recovery design.
- Select the file when opening its containing folder using a Windows shell API or
  safely constructed argument list; verify spaces and special characters.

## 4. Rebuild and release decision

Run source tests, lint and dependency checks. Produce a new identifiable preview
version and ZIP/hash, then run packaged and relocated smoke checks. Retest all
reported failures on the executable using disposable files, including physical
exFAT and safe disconnect scenarios. Check a genuinely clean Windows environment
without Python (for example an available VM or Windows Sandbox); the sanitized
launcher is useful evidence but does not replace that test.

Update acceptance results with the tested version/hash and retain old evidence.
Only consider release sign-off when the blockers and outstanding checks pass.
The next development work is this stabilization cycle, not another feature milestone.

## Implementation evidence and remaining gates

- Read-only deletion changes only that bit and restores it on failure. Cleanup and
  rename retry sharing/lock violations up to five attempts over one second; ACL
  denial is not blindly retried. Backup removal checks its recorded identity/state.
- Verified outcomes distinguish an incomplete Move (`copied_original_retained`),
  a completed Copy with cleanup warning (`cleanup_warning`), a completed Move with
  cleanup warning (`moved_cleanup_warning`), and unverified results (`needs_review`).
  Warning paths remain visible in History; they do not mark a batch completed.
- Volume capability checks skip stream enumeration only on confirmed non-stream
  filesystems. Stream loss is still refused; no metadata-stripping option was added.
- Grid drag flags are restored after Static movement disables them. Favorites,
  standard locations and drives now accept confirmed file drops. Gesture/viewport
  regressions pass; native entry/drop diagnostics are logged. The cause of the
  reported Details/Explorer native failure is not yet established: retest it before
  considering Fix 8 closed. This environment denies SetCursorPos even outside the
  sandbox, so real mouse/OLE verification could not be completed here.
- Missing Favorites offer removal; refresh recovers from a deleted current folder.
  Expected rejections log without tracebacks; per-file failures include paths/codes.
  Containing-folder requests use Explorer selection arguments. Cancellation stays
  visible and a requested exit waits for the current file and cleanup.

Physical exFAT, native Explorer/Details/Grid drags, disconnect, and a genuinely
clean Windows machine remain owner acceptance gates. See `STABILIZATION_REPORT.md`
for final local test/build evidence. Original findings are unchanged.

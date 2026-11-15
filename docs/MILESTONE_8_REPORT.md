# Milestone 8 verification report

Date: 2026-11-15 (Asia/Manila). Branch: `feature/windows-packaging`.
Build: `1.0.0-preview`, Windows x64, folder-based PyInstaller distribution.

## Automated evidence

- Environment: Windows 11 build 26200, Python 3.14.7 x64, PySide6 6.12.0,
  PyInstaller 6.22.3, hooks-contrib 2026.10, pytest 9.2.0, Ruff 0.17.5.
- Source suite: **100 tests passed, plus 8 subtests** through pytest.
- Ruff: passed for `app`, `tests`, and `tools`. Dependency consistency: passed.
- Added regression coverage: actual Windows exclusive file lock preserves the
  original and prevents publishing a destination; frozen executable-folder
  protection; local logs; frozen external-launch DLL-path restoration.
- Source isolated smoke: 11 checks passed.
- Packaged isolated smoke: 11 checks passed with frozen imports, from an unrelated
  temporary working directory, with Python/venv/Qt settings cleared and a
  Windows-only PATH. Runtime module paths were inside the bundle.
- Tested bundled PNG/PDF/text/DOCX/XLSX/PPTX previews and decoded a video frame.
- Exercised fixture-only verified copy, rename-on-conflict, move, rename, per-file
  history, and restart persistence of shortcuts, favorites, and view mode.
- Packaging review: Qt platform/image/multimedia plugins included. Icon and
  `1.0.0-preview` PE version resources present. Upstream license/metadata files
  and usage documentation accompany the package.

Final refreshed package: **11/11 passed** (`artifacts/packaged-final-smoke.json`).
ZIP extracted to a new temporary location: **11/11 passed**
(`artifacts/relocated-final-smoke.json`). Both used the clean-environment launcher.
PE inspection confirmed x64 machine type, Windows GUI subsystem, icon/group-icon
resources, and `asInvoker` execution privileges.

Folder package size: 180,067,730 bytes. Review ZIP size: 79,029,809 bytes.
Archive: `dist/FileSpace-1.0.0-preview-windows-x64.zip`.
SHA-256: `1f6a7deb89e9f9f3e765655c5ba5c952938605458c413c3c0e51106b784616f9`.

Generated raw reports live in ignored `artifacts/`;
the SHA-256 file inventory is in `build/package-manifest.json`.

## Safety/error handling review

- Source/destination and protected-path checks remain before confirmed mutations.
- Same-drive and cross-drive moves share staged SHA-256 verification before
  source removal; native named streams are copied/verified too.
- Conflict publication refuses unexpected overwrites. Explicit replacement keeps
  the old destination until the transfer completes; recovery paths are reported.
- Copy retains originals. Cancellation is between files. Journal failures stop
  later work and explain that earlier actions may already have completed.
- Rename refuses collisions and preserves the extension. Recycle uses Qt's
  native trash API with no permanent-delete fallback.
- Preview/parser and transfer work remains outside the GUI thread. Active previews
  are released before mutations. Partial failures are reported per file.
- Packaged application data stays outside the installation folder; the executable
  directory and bundled resources are protected from mutations.
- Bounded local error logs and an unexpected-error dialog address windowed builds
  without a terminal. External Open temporarily clears/restores the bundle DLL path.

No critical data-integrity failure was found in the automated scenarios. This is
not a guarantee against OS races, power loss, hardware faults, or untested codecs.
The known limitations document records those boundaries.

## Owner manual acceptance results

Owner testing on 2026-11-15 used the packaged ZIP extracted to `D:\Pkg`,
disposable fixtures in `D:\FS_TestLab`, NTFS drives C:/D: and an exFAT USB E:.
Most source fixtures were read-only. See the unmodified
[acceptance findings](../FileSpace_acceptance_findings.md) for reproduction details.

**Release status: BLOCKED.** Automated successes above remain valid only for their
covered scenarios. Manual testing found:

- Read-only Move and Replace leave incomplete cleanup / `needs_review` results.
- Plain-file copies to exFAT fail during staging-stream inspection.
- Actual internal and Explorer drag/drop fails in both views.
- Additional issues affect history clarity, missing-folder handling, logging,
  containing-folder selection, and cancellation feedback.

Navigation, filtering, selection, previews/audio, persistence, keyboard shortcuts,
protected paths, locked-file preservation, rename and native Recycle/restore
passed the reported scenarios. NTFS cross-drive metadata preservation passed.
Read-only operations and exFAT remain exceptions; these passes do not override
those failures. No-Python machine and disconnect-during-transfer checks remain
pending. The transient zero-byte staging lock is unconfirmed and needs reproduction.

## Delivery status

Milestone 8 packaging/tooling is implemented as a preview snapshot. This snapshot
and the owner findings are being committed to `feature/windows-packaging` for
review, without merging to the stable branch or uploading a release/binary.
Release sign-off is blocked until corrections and packaged retesting pass.
See [the prioritized remediation plan](ACCEPTANCE_REMEDIATION_PLAN.md).

# Preview limitations

- File transfers, rename, and recycling support regular files, not directory trees.
- Protected Windows/application/data/source locations, links/junctions/cloud reparse
  points, and encrypted/system files are excluded from mutating actions.
- Cross-drive and same-drive moves use staged copies and hashes. They require free
  space and are slower than a same-volume rename. Cancellation is between files.
- Filesystem operations and SQLite history are not one atomic transaction. Process
  termination or power loss can leave duplicates, staging/backup files, and pending
  history. There is no automatic recovery or undo. Review both paths before retrying.
- No silent overwrite occurs in the implemented publication path. Concurrent external
  edits can still race filesystem checks; this is not a sandbox against hostile actors.
- Named NTFS streams are preserved and verified. Destinations unable to preserve
  streams cause a safe failure rather than stripping them.
- GIF shows its first frame. Image dimensions are limited to 40 million pixels.
  Text is bounded to 100,000 bytes. Office files are bounded to 20 MiB compressed /
  64 MiB expanded; Office text is simplified and capped. XLSX shows the first sheet's
  first 100 rows and 20 columns, cached formulas only. PDF is capped at 50 MiB and
  one rendered page at a time; encrypted PDFs have no password-entry flow.
- Video support depends on bundled/system codecs and hardware. Tested video frames
  do not prove every encoding, audio device, or file container on every machine.
- Current-folder search does not recursively scan subdirectories. Grid uses icons,
  not generated image thumbnails. Only view mode persists; search/sort reset on restart.
- Case-only renames are refused. Rename preserves the final file extension.
- External Move requires an explicit selection. Outgoing drags from FileSpace are
  not supported; internal payloads are private to avoid bypassing confirmation.
- Only focused-file-view A–Z keywords are supported. There are no system-wide hooks.
- No installer, digital signing, auto-updater, or published GitHub release is supplied.
- Clean-machine launch, actual Explorer mouse/OLE interactions, Recycle Bin restore,
  physical cross-volume and disconnect scenarios remain manual release-gate checks.

The build is labeled `1.0.0-preview` pending that manual sign-off. UI refinement
can follow this milestone without changing the verified transfer engine.

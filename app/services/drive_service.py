"""Discover Windows standard locations and mounted volumes through Qt."""

from PySide6.QtCore import QStandardPaths, QStorageInfo


def standard_locations() -> list[tuple[str, str]]:
    """Use OS-provided destinations, including redirected known folders."""
    locations = QStandardPaths.StandardLocation
    return [
        (name, QStandardPaths.writableLocation(kind))
        for name, kind in (
            ("Home", locations.HomeLocation),
            ("Desktop", locations.DesktopLocation),
            ("Documents", locations.DocumentsLocation),
            ("Downloads", locations.DownloadLocation),
            ("Pictures", locations.PicturesLocation),
            ("Videos", locations.MoviesLocation),
        )
    ]


def available_drives() -> list[tuple[str, str]]:
    """Return ready mounted volumes without requesting elevated privileges."""
    return sorted(
        (f"{volume.displayName()} ({volume.rootPath()})", volume.rootPath())
        for volume in QStorageInfo.mountedVolumes()
        if volume.isValid() and volume.isReady()
    )

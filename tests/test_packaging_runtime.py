"""Runtime packaging guards and native file-lock regression checks."""

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.diagnostics import configure_logging
from app.filesystem.file_operations import build_plan, transfer_file
from app.filesystem.safety import SafetyPolicy, default_policy
from app.runtime import external_library_search, resource_path


class RuntimeTests(unittest.TestCase):
    def test_icon_resources_exist_in_source_layout(self):
        self.assertTrue(resource_path("icons/filespace.ico").is_file())
        self.assertTrue(resource_path("smoke/clip.mp4").is_file())

    def test_frozen_executable_directory_is_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            package = root / "package"
            package.mkdir()
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(package / "FileSpace.exe")):
                policy = default_policy(root / "state" / "filespace.sqlite3")
            self.assertIn(package, policy.roots)
            self.assertFalse(policy.allows_candidate(package / "FileSpace.exe"))

    def test_nonfrozen_external_launch_does_not_change_windows_dll_search(self):
        with patch.object(sys, "frozen", False, create=True), patch("app.runtime.ctypes.WinDLL", create=True) as windows:
            with external_library_search():
                pass
            windows.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows DLL API")
    def test_frozen_dll_search_is_restored_even_when_launch_fails(self):
        with patch.object(sys, "frozen", True, create=True), patch("app.runtime.ctypes.WinDLL") as windows:
            kernel = windows.return_value
            original_directory = "C:/bundle/_internal"
            def get_directory(size, buffer):
                if buffer is not None:
                    buffer.value = original_directory
                return len(original_directory) + 1
            kernel.GetDllDirectoryW.side_effect = get_directory
            kernel.SetDllDirectoryW.return_value = True
            with self.assertRaisesRegex(RuntimeError, "launch failed"), external_library_search():
                raise RuntimeError("launch failed")
            self.assertEqual(kernel.SetDllDirectoryW.call_count, 2)
            self.assertEqual(kernel.SetDllDirectoryW.call_args.args[0], original_directory)

    def test_local_log_records_errors_and_can_be_closed_for_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            logger = logging.getLogger("app")
            before = list(logger.handlers)
            try:
                path = configure_logging(Path(folder))
                logging.getLogger("app.test").error("Fixture diagnostic")
                self.assertIn("Fixture diagnostic", path.read_text(encoding="utf-8"))
            finally:
                for handler in list(logger.handlers):
                    if handler not in before:
                        logger.removeHandler(handler)
                        handler.close()

    @unittest.skipUnless(os.name == "nt", "Native Windows sharing lock")
    def test_real_locked_source_preserves_original_and_does_not_publish_copy(self):
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source, destination = root / "locked.txt", root / "destination"
            source.write_bytes(b"locked fixture")
            destination.mkdir()
            policy = SafetyPolicy([])
            plan = build_plan([str(source)], str(destination), policy)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel.CreateFileW
            create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            create.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = create(str(source), 0x80000000, 0, None, 3, 0x80, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            try:
                result = transfer_file(plan, plan.items[0], "move", policy)
                self.assertEqual(result.status, "failed")
                self.assertTrue(source.exists())
                self.assertFalse(list(destination.iterdir()))
            finally:
                kernel.CloseHandle(handle)
            self.assertEqual(source.read_bytes(), b"locked fixture")


if __name__ == "__main__":
    unittest.main()

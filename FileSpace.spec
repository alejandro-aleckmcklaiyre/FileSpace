# Reproducible Windows onedir build; run from the project directory.
from importlib.metadata import distribution
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

project = Path(SPECPATH)
datas = [(str(project / "app/resources"), "app/resources")]
runtime_distributions = [
    "PySide6", "PySide6_Essentials", "PySide6_Addons", "PySide6_Pdf",
    "shiboken6", "python-docx", "openpyxl", "python-pptx", "lxml", "pillow",
    "et_xmlfile", "typing_extensions", "xlsxwriter",
]
for name in runtime_distributions:
    datas += copy_metadata(name)
    package = distribution(name)
    for relative in package.files or []:
        lower = str(relative).lower()
        if "license" in lower or Path(lower).name.startswith(("copying", "notice")):
            path = Path(package.locate_file(relative))
            if path.is_file():
                datas.append((str(path), str(Path("licenses") / name / Path(relative).parent)))

analysis = Analysis(
    [str(project / "main.py")], pathex=[str(project)], binaries=[], datas=datas,
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["pytest", "ruff", "tkinter", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineCore"],
    noarchive=False,
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive, analysis.scripts, [], exclude_binaries=True, name="FileSpace",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon=str(project / "app/resources/icons/filespace.ico"),
    version=str(project / "packaging/version_info.txt"),
    uac_admin=False,
)
collection = COLLECT(
    executable, analysis.binaries, analysis.datas, strip=False, upx=False, name="FileSpace",
)

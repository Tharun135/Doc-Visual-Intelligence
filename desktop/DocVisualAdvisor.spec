# PyInstaller spec for Doc Visual Advisor Desktop
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]

block_cipher = None

datas = [
    (str(project_root / "rules" / "visual_rules.json"), "rules"),
    (str(project_root / "rules" / "knowledge_model.json"), "rules"),
    (str(project_root / "generators" / "siemens_theme.json"), "generators"),
]

hiddenimports = [
    "analyzers.section_splitter",
    "analyzers.text_extractor",
    "analyzers.visual_detector",
    "rules.rule_definitions",
    "generators.svg_flow_renderer",
    "generators.architecture_orchestrator",
    "generators.architecture_renderer",
    "generators.screenshot_specification",
]

a = Analysis(
    [str(project_root / "desktop" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DocVisualAdvisor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
runtime = root / "runtime/out-win64"

datas = [
    (str(root / "copper_and_code_studio/gen/widgets.json"), "copper_and_code_studio/gen"),
    (str(root / "copper_and_code_studio/gen/completion.json"), "copper_and_code_studio/gen"),
    (str(root / "copper_and_code_studio/translations"), "copper_and_code_studio/translations"),
    (str(root / "copper_and_code_studio/boards"), "copper_and_code_studio/boards"),
    (str(root / "copper_and_code_studio/blocks"), "copper_and_code_studio/blocks"),
    (str(root / "copper_and_code_studio/icon.ico"), "copper_and_code_studio"),
    (str(root / "runtime/display_driver.py"), "runtime"),
    (str(root / "runtime/program"), "runtime/program"),  # programs without pages
    (str(root / "native/lvsim"), "native/lvsim"),
    # Only what is needed to build the C target: no tests, demos, documentation or scripts.
    (str(root / ".reference/lvgl-bindings/lvgl/src"), ".reference/lvgl-bindings/lvgl/src"),
    *[(str(root / ".reference/lvgl-bindings/lvgl" / name), ".reference/lvgl-bindings/lvgl") for name in ("lvgl.h", "lvgl_private.h", "lv_version.h", "LICENCE.txt", "COPYRIGHTS.md")],
    (str(root / ".reference/lvgl-bindings/lv_conf.h"), ".reference/lvgl-bindings"),
    (str(root / "docs/target.md"), "docs"),
    (str(root / "docs/boards.md"), "docs"),
    (str(root / "docs/boards.it.md"), "docs"),
    (str(root / "docs/windows-c.md"), "docs"),
    (str(root / "packaging/NOTICE.txt"), "share/doc/copper-and-code-studio"),
    (str(root / "LICENSE"), "share/doc/copper-and-code-studio"),
    (str(root / "LICENSE-MIT.txt"), "share/doc/copper-and-code-studio"),
    (str(root / "LICENSING.md"), "share/doc/copper-and-code-studio"),
    (str(root / "packaging/licenses"), "share/doc/copper-and-code-studio/licenses"),
    (str(root / "copper_and_code_studio/gen/output/licenses"), "copper_and_code_studio/gen/output/licenses"),
    (str(root / "THIRD_PARTY.md"), "share/doc/copper-and-code-studio"),
]
for name in ("lvsim-runtime.exe", "lvsim-standalone.exe", "lvsim-onefile.exe", "mpy-cross.exe", "SDL2.dll", "liblvgl.a"):
    datas.append((str(runtime / name), "runtime/out-win64"))
datas.append((str(root / "runtime/out/lvsim-onefile"), "runtime/out"))  # games for Linux built on Windows
datas += [(str(root / "runtime/out-web" / name), "runtime/out-web") for name in ("micropython.mjs", "micropython.wasm")]
datas.append((str(root / "runtime/web"), "runtime/web"))
for name in ("include", "lib"):
    datas.append((str(runtime / "SDL2" / name), f"runtime/out-win64/SDL2/{name}"))

analysis = Analysis(
    [str(root / "packaging/launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("mpremote") + collect_submodules("qtawesome"),
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "hypothesis"],
    noarchive=False,
)
# The PyInstaller hook adds every QtAwesome font: the others have different licences and are not needed.
analysis.datas = [item for item in analysis.datas if "qtawesome/fonts" not in item[0].replace("\\", "/") or "materialdesignicons6" in item[0]]
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="Copper_and_Code_Studio", console=False, icon=str(root / "copper_and_code_studio/icon.ico"))
collection = COLLECT(exe, analysis.binaries, analysis.datas, name="Copper_and_Code_Studio")

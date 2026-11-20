import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

from .core.i18n import DEFAULT_LANGUAGE, LANGUAGES, device_error_text, set_language, tr
from .platform import RUNTIME_ENTRY, exe_name, runtime_environment, runtime_path


def _generation(project, target, output):
    if target == "c":
        from .gen.gen_c import generate_c
        from .build.c_compiler import compile_c
        generated = generate_c(project, output)
        compile_c(output)
        result = output / exe_name("app")
    else:
        from .gen.project_gen import generate_project
        from .build.compiler import compile_python
        generated = generate_project(project, output)
        compile_python(output)
        result = runtime_path()
    for warning in generated["warnings"]:
        print(tr("Warning: {warning}", warning=warning), file=sys.stderr)
    return result


def _board_export(project, output, profile_id=None, force=False):
    from .core.boards import portable_profile
    from .gen.board_gen import changed_exports, export_board
    if not profile_id and project.board is None:
        raise ValueError(device_error_text("device.profile.required"))
    profile = portable_profile(_profile(profile_id) if profile_id else project.board)
    changed = changed_exports(output)
    if changed and not force:
        raise ValueError(tr("Files changed after the last export: {files}. Use --force to overwrite them.", files=", ".join(changed)))
    generated = export_board(project, profile, output)
    for warning in generated["warnings"]:
        print(tr("Warning: {warning}", warning=warning), file=sys.stderr)
    return output


def _web(project, output, port, open_browser):
    """Build the web version and serve it until Ctrl+C is pressed."""
    import time
    import webbrowser
    from .build.web import build_web, serve
    folder = build_web(project, output)
    server, url = serve(folder, port)
    print(tr("Web version in {path}", path=folder))
    print(tr("Open at {url} — Ctrl+C to stop", url=url), flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    finally:
        server.shutdown()


def _profile(profile_id=None):
    from .core.boards import ProfileStore, builtin_profiles
    if profile_id:
        profile = ProfileStore().get(profile_id)
        if profile is None:
            raise ValueError(f"profile.not-found:{profile_id}")
        return profile
    return builtin_profiles()[0]


def _device_command(args, parser):
    from .core.model import Project
    from .device.service import DeviceSession
    session = DeviceSession()
    if args.device_command == "list":
        print(json.dumps(session.list_ports(), ensure_ascii=False, indent=2))
        return 0
    project = Project.load(args.project) if getattr(args, "project", None) else None
    profile = copy.deepcopy(project.board) if project and project.board else _profile(getattr(args, "board_profile", None))
    session.connect(args.port, profile)
    if args.device_command == "info":
        print(json.dumps(session.info(), ensure_ascii=False, indent=2))
    elif args.device_command == "upload":
        result = session.upload(project, output_dir=args.output)
        print(json.dumps({"appPath": result["appPath"], "files": result["files"], "warnings": result["warnings"]}, ensure_ascii=False, indent=2))
    elif args.device_command == "run":
        result = session.run(project, output_dir=args.output)
        if result["output"]:
            print(result["output"], end="" if result["output"].endswith("\n") else "\n")
        print(tr("Board application started; the LVGL timer remains active after bootstrap."))
    elif args.device_command == "stop":
        print(session.stop(), end="")
        print(tr("Board stopped; the last image may remain visible."))
    elif args.device_command == "reset":
        session.restart()
    elif args.device_command == "repl":
        return session.repl()
    elif args.device_command == "autostart-install":
        print(json.dumps(session.install_autostart(project), ensure_ascii=False, indent=2))
    elif args.device_command == "autostart-remove":
        session.remove_autostart(project)
        print(tr("Autostart removed"))
    return 0


def _visual_tests(args, project):
    from .build.visual import ERROR, FAILED, MISSING, PASSED, UPDATED, baseline_dir, run_visual_tests
    directory = args.baseline or baseline_dir(args.project.resolve(), project)
    results = run_visual_tests(project, directory, update=args.update, threshold=args.threshold, pages=args.page, design_only=args.design_only, scenarios=args.scenario)
    messages = {
        PASSED: "ok",
        UPDATED: tr("baseline updated"),
        MISSING: tr("baseline missing: run with --update"),
        FAILED: tr("different"),
        ERROR: tr("error"),
    }
    for result in results:
        line = f"{result.page}: {messages[result.status]}"
        if result.status == FAILED:
            line += " " + tr("({count} pixels in {box}), see {path}", count=result.different, box=result.box, path=result.message)
        elif result.status == ERROR:
            line += f": {result.message}"
        print(line)
    return 0 if all(result.status in (PASSED, UPDATED) for result in results) else 1


def _board_command(args):
    from .core.boards import ProfileError, ProfileStore, profile_error_text, write_profile_file

    store = ProfileStore()
    if args.board_command == "list":
        for profile in store.profiles():
            print(f"{profile['id']}\t{profile['logicalWidth']}x{profile['logicalHeight']}\t{profile['origin']}\t{profile['name']}")
        return 0
    if args.board_command == "import":
        try:
            profile = store.import_profile(args.file, replace=args.replace)
        except ProfileError as exc:
            raise ValueError(profile_error_text(exc) + (" " + tr("Use --replace to replace it.") if exc.code == "profile.import.exists" else "")) from None
        print(profile["id"])
        return 0
    profile = store.get(args.board)
    if profile is None:
        raise ValueError(tr("Unknown board {board}: see `board list`.", board=args.board))
    if args.board_command == "export":
        print(write_profile_file(profile, args.file))
        return 0
    store.delete(profile["id"])
    store.save()
    print(tr("{board} hidden: the Board Profile Manager restores it.", board=profile["id"]) if profile["origin"] == "builtin" else tr("{board} deleted.", board=profile["id"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["_mpremote"]:
        import runpy
        sys.argv = [sys.argv[0], *arguments[1:]]
        runpy.run_module("mpremote", run_name="__main__")
        return 0
    language_parser = argparse.ArgumentParser(add_help=False)
    language_parser.add_argument("--language", choices=tuple(LANGUAGES), default=DEFAULT_LANGUAGE)
    language_args, _remaining = language_parser.parse_known_args(arguments)
    set_language(language_args.language)
    parser = argparse.ArgumentParser(prog="copper-and-code-studio", description=tr("Visual IDE for LVGL, simulator and MicroPython boards"))
    parser.add_argument("--language", choices=tuple(LANGUAGES), default=DEFAULT_LANGUAGE, help=tr("Message language"))
    parser.add_argument("--version", action="store_true")
    commands = parser.add_subparsers(dest="command")
    for name in ("generate", "run", "build"):
        command = commands.add_parser(name)
        command.add_argument("project", type=Path)
        command.add_argument("--target", choices=("micropython", "c", "board") if name == "generate" else ("micropython", "c"), default="micropython")
        if name in ("generate", "build"):
            command.add_argument("--output", type=Path)
        if name == "generate":
            command.add_argument("--board-profile", help=tr("Board for --target board, if different from the project's"))
            command.add_argument("--force", action="store_true", help=tr("With --target board, also overwrites changed files"))
        if name == "build":
            command.add_argument("--profile", choices=("debug", "release"), default="debug")
            command.add_argument("--single-file", action="store_true", help=tr("A single executable to send to players; needs --profile release"))
            command.add_argument("--for", dest="system", choices=("linux", "windows"), help=tr("System of the single file, if different from this one"))
            command.add_argument("--web", action="store_true", help=tr("Browser version: a folder to publish on a static host"))
    web = commands.add_parser("web", help=tr("Build the browser version and open it"), description=tr("Build the browser version and open it"))
    web.add_argument("project", type=Path)
    web.add_argument("--output", type=Path)
    web.add_argument("--port", type=int, default=0)
    web.add_argument("--no-browser", action="store_true", help=tr("Do not open the browser, only show the address"))
    commands.add_parser("mcp", help=tr("Start the MCP server for AI agents on stdio"), description=tr("Start the MCP server for AI agents on stdio"))
    visual = commands.add_parser("test", help=tr("Compare pages with the reference images"), description=tr("Compare pages with the reference images"))
    visual.add_argument("project", type=Path)
    visual.add_argument("--update", action="store_true", help=tr("Rewrite the reference images"))
    visual.add_argument("--baseline", type=Path, help=tr("Folder of the reference images"))
    visual.add_argument("--threshold", type=int, default=0, help=tr("Different pixels allowed per page"))
    visual.add_argument("--page", action="append", help=tr("Test only this page; repeatable"))
    visual.add_argument("--scenario", action="append", help=tr("Test only this scenario; repeatable"))
    visual.add_argument("--design-only", action="store_true", help=tr("Do not run the project code"))
    selftest = commands.add_parser("selftest", help=tr("Use the IDE by itself and report what works"), description=tr("Use the IDE by itself and report what works"))
    selftest.add_argument("scenario", nargs="*", help=tr("Scenarios to run; all of them without this"))
    selftest.add_argument("--show", action="store_true", help=tr("Show the IDE while it is used"))
    selftest.add_argument("--slow", type=int, default=None, metavar="MS", help=tr("Pause after each action, in milliseconds; 400 with --show"))
    selftest.add_argument("--output", type=Path, help=tr("Folder of the report"))
    selftest.add_argument("--list", action="store_true", help=tr("List the scenarios"))
    boards = commands.add_parser("board", help=tr("Boards of the IDE: list, import from a file, export, delete"), description=tr("Boards of the IDE: list, import from a file, export, delete"))
    board_commands = boards.add_subparsers(dest="board_command", required=True)
    board_commands.add_parser("list")
    board_import = board_commands.add_parser("import", help=tr("Add the board defined in a .json file"))
    board_import.add_argument("file", type=Path)
    board_import.add_argument("--replace", action="store_true", help=tr("Replace a board of the same id that is not built in"))
    board_export = board_commands.add_parser("export", help=tr("Write a board to a .json file"))
    board_export.add_argument("board")
    board_export.add_argument("file", type=Path)
    board_delete = board_commands.add_parser("delete", help=tr("Remove a board; a built-in one is hidden"))
    board_delete.add_argument("board")
    device = commands.add_parser("device", help=tr("MicroPython board operations"), description=tr("MicroPython board operations"))
    device_commands = device.add_subparsers(dest="device_command", required=True)
    device_commands.add_parser("list")
    for name in ("info", "stop", "reset", "repl"):
        command = device_commands.add_parser(name)
        command.add_argument("--port", required=True)
        command.add_argument("--board-profile")
    for name in ("upload", "run", "autostart-install", "autostart-remove"):
        command = device_commands.add_parser(name)
        command.add_argument("project", type=Path)
        command.add_argument("--port", required=True)
        command.add_argument("--board-profile")
        if name in ("upload", "run"):
            command.add_argument("--output", type=Path)
    args = parser.parse_args(arguments)
    if args.version:
        from . import __version__
        print(f"Copper and Code Studio {__version__}")
        return 0
    if args.command == "selftest":
        from .selftest import main as selftest_main

        slow = args.slow if args.slow is not None else 400 if args.show else 0
        return selftest_main(args.scenario, args.show, slow, args.output, args.list)
    if args.command == "mcp":
        from .mcp_server import is_enabled, serve
        if not is_enabled():
            parser.exit(1, "copper-and-code-studio: " + tr("The MCP server is off: turn it on under Settings → MCP Server for AI Agents.") + "\n")
        return serve()
    if args.command:
        from .build.compiler import CompileError
        from .core.model import Project
        from .device.service import DeviceError
        try:
            if args.command == "device":
                return _device_command(args, parser)
            if args.command == "board":
                return _board_command(args)
            project = Project.load(args.project)
            base = args.project.resolve().parent
            if args.command == "test":
                return _visual_tests(args, project)
            if args.command == "generate" and args.target == "board":
                print(_board_export(project, args.output or base / "export_py", args.board_profile, args.force))
                return 0
            if args.command == "generate":
                output = args.output or base / "build" / ("c" if args.target == "c" else "py")
                print(_generation(project, args.target, output))
                return 0
            if args.command == "run":
                output = base / "build" / ("c" if args.target == "c" else "py")
                executable = _generation(project, args.target, output)
                env = runtime_environment()
                command = [str(executable)] + (RUNTIME_ENTRY if args.target == "micropython" else [])
                return subprocess.run(command, cwd=output, env=env).returncode
            if args.command == "web":
                return _web(project, args.output or base / "dist", args.port, not args.no_browser)
            if args.web:
                from .build.web import build_web
                print(build_web(project, args.output or base / "dist") / "index.html")
                return 0
            from .build.release import build_release
            windows = None if args.system is None else args.system == "windows"
            print(build_release(project, args.target, args.output or base / "dist", args.profile, args.single_file, windows))
            return 0
        except KeyboardInterrupt:
            return 130
        except DeviceError as exc:
            parser.exit(1, f"copper-and-code-studio: {device_error_text(exc.code, exc.output)}\n" + "".join(f"warning: {warning}\n" for warning in exc.warnings))
        except (OSError, ValueError, RuntimeError, CompileError) as exc:  # RuntimeError: manifest, simulator, Release build
            parser.exit(1, f"copper-and-code-studio: {exc}\n")

    from PySide6.QtWidgets import QApplication
    from .ui import theme
    from .ui.main_window import MainWindow

    if sys.platform == "win32":
        # Without its own identity the taskbar shows the icon of pythonw.exe, which hosts the IDE.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CopperAndCode.CopperAndCodeStudio")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setWindowIcon(theme.app_icon())
    window = MainWindow()
    window.show()
    return app.exec()

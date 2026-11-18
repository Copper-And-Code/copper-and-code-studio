"""Where are the tests blind? Small changes to the code, one at a time, and the tests that should notice.

    .venv/bin/python tools/mutation_probe.py                   # every module of TARGETS, 25 changes each
    .venv/bin/python tools/mutation_probe.py ui/files.py 60    # one module, 60 changes

Each change ("mutant") turns a comparison around, swaps and/or, drops a not, changes a constant
or a returned value. For each, the tests of that module run; a change that no test notices
"survives", and its line is a place where the tests do not look. The report goes to
build/manual/mutation/<module>.txt. The work is done in a copy of the repository in a temporary
folder: the files of the repository are never changed.
"""
import ast
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "build" / "manual" / "mutation"
# module (under lvgl_mpy_studio) → the tests that should notice a change in it
TARGETS = {
    "ui/files.py": ["tests/test_files_panel.py"],
    "ui/properties/panel.py": ["tests/test_properties.py"],
    "ui/designer/scene.py": ["tests/test_designer.py", "tests/test_arrange.py"],
    "ui/language.py": ["tests/test_i18n.py", "tests/test_window_checks.py", "tests/test_board_support.py"],
    "ui/main_tree.py": ["tests/test_main_window.py", "tests/test_modules_gui.py"],
    "core/names.py": ["tests/test_validation.py", "tests/test_model.py"],
    "core/vt.py": ["tests/test_terminal.py"],
}
SWAPS = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}


def mutation_points(tree):
    """(node, kind) of every place a change can be made, in the order of the file."""
    points = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and type(node.ops[0]) in SWAPS:
            points.append((node, "compare"))
        elif isinstance(node, ast.BoolOp):
            points.append((node, "boolop"))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            points.append((node, "not"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            points.append((node, "bool"))
        elif isinstance(node, ast.Constant) and type(node.value) is int and not isinstance(node.value, bool):
            points.append((node, "number"))
        elif isinstance(node, ast.Return) and node.value is not None:
            points.append((node, "return"))
    return sorted(points, key=lambda point: (point[0].lineno, point[0].col_offset))


def mutate(source, index):
    """The source with the index-th change made, and a description of it."""
    tree = ast.parse(source)
    node, kind = mutation_points(tree)[index]
    line = node.lineno
    if kind == "compare":
        before = type(node.ops[0]).__name__
        node.ops[0] = SWAPS[type(node.ops[0])]()
        what = f"{before} → {type(node.ops[0]).__name__}"
    elif kind == "boolop":
        before = type(node.op).__name__
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        what = f"{before} → {type(node.op).__name__}"
    elif kind == "not":
        replacement = node.operand
        for parent in ast.walk(tree):
            for field, value in ast.iter_fields(parent):
                if value is node:
                    setattr(parent, field, replacement)
                elif isinstance(value, list) and node in value:
                    value[value.index(node)] = replacement
        what = "not dropped"
    elif kind == "bool":
        node.value = not node.value
        what = f"{not node.value} → {node.value}"
    elif kind == "number":
        node.value += 1
        what = f"{node.value - 1} → {node.value}"
    else:
        node.value = ast.Constant(value=None)
        what = "returns None"
    return ast.unparse(tree), line, what


def copy_repository(target):
    ignore = shutil.ignore_patterns(".venv", "build", "dist", "cache", ".git", "__pycache__", "*.mp4", "out-*", "lvgl-mpy-studio-selftest", ".reference")
    shutil.copytree(ROOT, target, ignore=ignore, symlinks=True)
    for heavy in ("runtime/out", ".reference"):
        source = ROOT / heavy
        if source.exists():
            (target / heavy).unlink(missing_ok=True) if (target / heavy).is_symlink() else shutil.rmtree(target / heavy, ignore_errors=True)
            (target / heavy).parent.mkdir(parents=True, exist_ok=True)
            os.symlink(source, target / heavy)


def run_tests(copy, tests, seconds=300):
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(copy)}
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-p", "no:warnings", *tests], cwd=copy, env=environment, capture_output=True, text=True, timeout=seconds)
    except subprocess.TimeoutExpired:
        return "killed (timeout)"
    return "survived" if result.returncode == 0 else "killed"


def probe(module, count, chance):
    tests = TARGETS[module]
    with tempfile.TemporaryDirectory(prefix="lms-mutation-") as folder:
        copy = Path(folder) / "repo"
        copy_repository(copy)
        path = copy / "lvgl_mpy_studio" / module
        original = path.read_text(encoding="utf-8")
        if run_tests(copy, tests) != "survived":
            return [f"{module}: the tests fail without any change; nothing measured"]
        points = mutation_points(ast.parse(original))
        chosen = sorted(chance.sample(range(len(points)), min(count, len(points))))
        lines = []
        for index in chosen:
            mutated, line, what = mutate(original, index)
            path.write_text(mutated, encoding="utf-8")
            try:
                verdict = run_tests(copy, tests)
            finally:
                path.write_text(original, encoding="utf-8")
            lines.append((verdict, line, what, original.splitlines()[line - 1].strip()))
            print(f"  {verdict:18} {module}:{line} {what}", flush=True)
    survived = [entry for entry in lines if entry[0] == "survived"]
    report = [f"{module}: {len(lines)} changes of {len(points)} possible, {len(lines) - len(survived)} noticed by {', '.join(tests)}, {len(survived)} not", ""]
    report += [f"{line:5} {what:20} {text[:110]}" for _verdict, line, what, text in survived]
    return report


def main():
    modules = [sys.argv[1]] if len(sys.argv) > 1 else list(TARGETS)
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    chance = random.Random(int(os.environ.get("LMS_MUTATION_SEED", "1")))
    REPORTS.mkdir(parents=True, exist_ok=True)
    summary = []
    for module in modules:
        started = time.monotonic()
        print(f"{module}:", flush=True)
        report = probe(module, count, chance)
        (REPORTS / (module.replace("/", "_") + ".txt")).write_text("\n".join(report) + "\n", encoding="utf-8")
        summary.append(report[0] + f" ({time.monotonic() - started:.0f} s)")
    print("\n" + "\n".join(summary))


if __name__ == "__main__":
    main()

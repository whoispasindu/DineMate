import ast
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "vision" / "worker.py"


def test_preview_window_can_show_and_close() -> None:
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    preview = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Preview")
    methods = {n.name for n in preview.body if isinstance(n, ast.FunctionDef)}
    assert {"__init__", "show", "close"} <= methods


def test_module_functions_have_no_unreachable_nested_methods() -> None:
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    for function in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
        nested = [n.name for n in ast.walk(function) if isinstance(n, ast.FunctionDef) and n is not function]
        assert all(not name.startswith("close") for name in nested), function.name

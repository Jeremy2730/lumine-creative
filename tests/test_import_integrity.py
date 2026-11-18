"""Integridad de importaciones del proyecto (análisis estático; no necesita Tk ni CustomTkinter).

Motivo: un archivo de producción puede quedar sobrescrito por otro (p. ej. un test copiado encima de
``tools/remove/dialog.py``). Las pruebas con Tk se omiten sin pantalla y ``import`` nunca se ejecuta,
así que el fallo solo aparecía al arrancar (``ImportError: cannot import name 'RemoveDialog'``).
Aquí se comprueba, leyendo el código, que cada ``from <módulo del proyecto> import <nombre>`` apunta a
algo que ese módulo realmente define, y que ningún archivo de producción contiene código de pruebas.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("app", "config", "core", "gui", "tools")


def _production_files() -> list[Path]:
    files = [ROOT / "main.py"]
    for package in PACKAGES:
        files += sorted((ROOT / package).rglob("*.py"))
    return [f for f in files if f.exists()]


def _module_path(dotted: str) -> Path | None:
    base = ROOT.joinpath(*dotted.split("."))
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _defined_names(path: Path) -> set[str]:
    """Nombres de primer nivel (incluye los de ``if``/``try`` de primer nivel y los reexportados)."""
    names: set[str] = set()

    def visit(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for sub in ast.walk(target):
                        if isinstance(sub, ast.Name):
                            names.add(sub.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    names.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(node, ast.If):
                visit(node.body)
                visit(node.orelse)
            elif isinstance(node, ast.Try):
                visit(node.body)
                for handler in node.handlers:
                    visit(handler.body)
                visit(node.orelse)
                visit(node.finalbody)

    visit(ast.parse(path.read_text(encoding="utf-8")).body)
    return names


def _broken_imports() -> list[str]:
    broken: list[str] = []
    cache: dict[Path, set[str]] = {}
    for file in _production_files():
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
                continue
            if node.module.split(".")[0] not in PACKAGES:
                continue
            target = _module_path(node.module)
            where = f"{file.relative_to(ROOT).as_posix()}:{node.lineno}"
            if target is None:
                broken.append(f"{where}: no existe el módulo {node.module}")
                continue
            names = cache.setdefault(target, _defined_names(target))
            for alias in node.names:
                if alias.name == "*" or alias.name in names:
                    continue
                if _module_path(f"{node.module}.{alias.name}") is not None:  # es un submódulo
                    continue
                broken.append(f"{where}: «{alias.name}» no está definido en {node.module}")
    return broken


def test_every_project_import_points_to_something_that_exists():
    assert _broken_imports() == []


def test_production_files_contain_no_test_code():
    offenders = []
    for file in _production_files():
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            )
            if any(name.split(".")[0] in ("pytest", "tests") for name in imported):
                offenders.append(f"{file.relative_to(ROOT).as_posix()}:{node.lineno}")
    assert offenders == []


def test_the_remove_window_class_exists_where_the_main_window_imports_it():
    dialog = _module_path("tools.remove.dialog")
    assert dialog is not None and "RemoveDialog" in _defined_names(dialog)

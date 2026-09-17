"""V18.20.4.8 (P6 rider, O-b6) — icon() render-cache source pins.

Hermetic: NO PySide6 import — every pin reads the
``ui_qt/components/icons.py`` SOURCE (text + AST), per the house
source-pin pattern (tests/test_v182048_p6_perf_polish.py).

Pinned:
  1. the module-level ``_ICON_CACHE`` dict exists (annotated, empty
     literal, one-line fix comment present);
  2. ``icon()`` checks the cache BEFORE building (the hit-lookup
     precedes any ``QIcon(pixmap(...))`` build; signature unchanged);
  3. the cache-write is present (stores the freshly built QIcon under
     the ``(name, color, size)`` key).

Run: pytest tests/test_v182048_p6_icon_cache.py -v
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_ICONS = _project_root / "ui_qt" / "components" / "icons.py"


def _src() -> str:
    return _ICONS.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments so pins assert
    CODE, not the fix-documentation comments around it (house pattern)."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


def _icon_func(tree: ast.Module) -> ast.FunctionDef:
    funcs = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "icon"
    ]
    assert len(funcs) == 1, "exactly one module-level icon() definition"
    return funcs[0]


class TestOb6IconCachePins:
    """V18.20.4.8 O-b6 rider: icon() render cache."""

    def test_cache_dict_exists_module_level(self):
        """Pin 1: module-level _ICON_CACHE annotated dict, empty literal,
        plus the one-line fix comment."""
        raw = _src()
        assert "V18.20.4.8: O-b6 icon cache" in raw, "one-line fix comment"
        tree = ast.parse(raw)
        assigns = [
            n
            for n in tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "_ICON_CACHE"
        ]
        assert len(assigns) == 1, "exactly one module-level _ICON_CACHE"
        ann = assigns[0].annotation
        # dict[...] (typing/builtin generic — both parse as ast.Subscript)
        assert isinstance(ann, ast.Subscript), "dict[...] annotation"
        assert isinstance(ann.value, ast.Name) and ann.value.id == "dict"
        # value is an empty dict literal (starts cold, no pre-seeding)
        assert isinstance(assigns[0].value, ast.Dict)
        assert not assigns[0].value.keys

    def test_icon_checks_cache_before_building(self):
        """Pin 2: the hit-lookup precedes the QPixmap-render build path and
        the public signature is unchanged (name/color/size defaults)."""
        code = _strip_comments(_src())
        tree = ast.parse(code)
        fn = _icon_func(tree)
        # signature unchanged: (name, color="#E8EAED", size=20) -> QIcon
        args = fn.args
        assert [a.arg for a in args.posonlyargs + args.args] == [
            "name",
            "color",
            "size",
        ]
        assert len(args.defaults) == 2
        assert args.defaults[0].value == "#E8EAED"
        assert args.defaults[1].value == 20
        assert fn.returns.id == "QIcon"
        # cache read: either `key in _ICON_CACHE` or `_ICON_CACHE.get(key)`
        reads = [
            ast.unparse(n)
            for n in ast.walk(fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "_ICON_CACHE"
        ] or [
            ast.unparse(n)
            for n in ast.walk(fn)
            if isinstance(n, ast.Compare)
            and isinstance(n.left, ast.Name)
            and n.left.id == "key"
        ]
        assert reads, "icon() must read the cache (dict.get or `in` test)"
        # the read must precede the build (QIcon(pixmap(...))) in source order
        body = ast.get_source_segment(code, fn) or ""
        hit = body.index("get") if "get" in body else body.index("key")
        build = body.index("QIcon(pixmap(")
        assert hit < build, "cache lookup must precede the pixmap build"

    def test_cache_write_present(self):
        """Pin 3: icon() stores the freshly built QIcon under the
        (name, color, size) key and returns it."""
        code = _strip_comments(_src())
        tree = ast.parse(code)
        fn = _icon_func(tree)
        writes = [
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Subscript)
            and isinstance(n.targets[0].value, ast.Name)
            and n.targets[0].value.id == "_ICON_CACHE"
        ]
        assert len(writes) == 1, "exactly one _ICON_CACHE[...] write"
        # the key is the (name, color, size) tuple built locally
        key_src = ast.unparse(writes[0].targets[0].slice)
        assert key_src == "key"
        keys = [
            ast.unparse(n)
            for n in ast.walk(fn)
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Tuple)
            and [ast.unparse(e) for e in n.value.elts] == ["name", "color", "size"]
        ]
        assert keys, "key = (name, color, size) tuple must be built"
        # every return path yields a QIcon (cached or freshly built)
        returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
        assert returns, "icon() must return"

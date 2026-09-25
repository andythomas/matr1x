# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
Snapshot test for the stable (Supported) public API.

The Supported API is defined by the ``reference`` section of
``great-docs.yml``. This test resolves every listed item, serializes its
signature (parameter names, kinds - i.e. the position of ``/`` and ``*``
- defaults and annotations) and compares it against the snapshot stored
in ``tests/data/public_api_snapshot.json``.

Compatibility rules (snapshot -> current):

Breaking changes (the test fails):

- an item is removed from the reference or no longer importable
- an item changes kind (function/class/enum/property/constant)
- a parameter or class member is removed
- a positional parameter is renamed, reordered or restricted
  (e.g. positional-or-keyword -> positional-only or keyword-only)
- an optional parameter becomes required
- a default value changes
- ``*args`` or ``**kwargs`` is removed
- a constant value changes
- an enum member is removed

Non-breaking changes (the test passes, a note is printed):

- a new item is listed in the reference
- a new optional parameter is added (keyword-only, or appended to the
  positional block)
- a required parameter becomes optional
- a parameter kind is relaxed (positional-only -> positional-or-keyword,
  keyword-only -> positional-or-keyword)
- ``*args`` or ``**kwargs`` is added
- a new class member or enum member is added
- an annotation changes

Regenerate the snapshot after an intended API change with::

    MATR1X_UPDATE_API_SNAPSHOT=1 uv run pytest tests/test_public_api.py
"""

from __future__ import annotations

import enum
import importlib
import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest
from yaml12 import read_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GREAT_DOCS_YML = REPO_ROOT / "great-docs.yml"
SNAPSHOT_FILE = Path(__file__).resolve().parent / "data" / "public_api_snapshot.json"
UPDATE_ENV = "MATR1X_UPDATE_API_SNAPSHOT"

_POSITIONAL_KINDS = ("positional_only", "positional_or_keyword")
_RELAXING_KIND_CHANGES = {
    ("positional_only", "positional_or_keyword"),
    ("keyword_only", "positional_or_keyword"),
}


def _load_reference() -> tuple[str, dict[str, bool]]:
    """
    Parse the reference section of great-docs.yml.

    Returns
    -------
    tuple[str, dict[str, bool]]
        The module root (``module`` key) and a mapping of item name
        (``module:qualname``) to whether its members are documented
        (``members`` is not ``false``).
    """
    config = read_yaml(GREAT_DOCS_YML)
    if not isinstance(config, dict):
        msg = "great-docs.yml must contain a mapping at the top level"
        raise ValueError(msg)
    module_root = config.get("module", "matr1x")
    items: dict[str, bool] = {}
    for section in config.get("reference", []):
        for entry in section.get("contents", []):
            if isinstance(entry, str):
                name, members = entry, True
            else:
                name = entry["name"]
                members = entry.get("members", True)
            items[name] = members
    return module_root, items


def _resolve_item(name: str, module_root: str) -> tuple[Any, Any]:
    """Return (object, parent) for a ``module:qualname`` reference."""
    module_name, _, qualname = name.partition(":")
    parent: Any = importlib.import_module(f"{module_root}.{module_name}")
    obj = parent
    for part in qualname.split("."):
        parent = obj
        obj = getattr(obj, part)
    return obj, parent


def _param_dict(param: inspect.Parameter) -> dict[str, str | None]:
    """Serialize one signature parameter to a JSON-friendly dict."""
    default = None if param.default is inspect.Parameter.empty else repr(param.default)
    annotation = None if param.annotation is inspect.Parameter.empty else repr(param.annotation)
    return {
        "name": param.name,
        "kind": param.kind.name.lower(),
        "default": default,
        "annotation": annotation,
    }


def _signature(obj: Any) -> list[dict[str, str | None]]:
    """Serialize the parameters of a callable or class constructor."""
    return [_param_dict(p) for p in inspect.signature(obj).parameters.values()]


def _method_params(func: Any) -> list[dict[str, str | None]]:
    """Serialize a method signature, dropping the leading self/cls."""
    params = _signature(func)
    if params and params[0]["name"] in ("self", "cls"):
        params = params[1:]
    return params


def _class_init_params(cls: type) -> list[dict[str, str | None]]:
    """Serialize a class constructor, tolerating Qt builtin quirks."""
    init = getattr(cls, "__init__", None)
    if init is not None and init is not object.__init__:
        try:
            return _method_params(init)
        except (TypeError, ValueError):
            pass
    try:
        return _signature(cls)
    except (TypeError, ValueError):
        return []


def _canonical_value(value: Any) -> str:
    """Return a run-stable string form of a constant value."""
    if isinstance(value, (set, frozenset)):
        return "{" + ", ".join(sorted(repr(v) for v in value)) + "}"
    return repr(value)


def _class_members(cls: type) -> dict[str, dict[str, Any]]:
    """
    Serialize the public members defined on ``cls`` itself.

    Inherited members are excluded: they are covered by the entry of the
    base class (or by the third-party base, e.g. Qt or pymeasure).
    """
    members: dict[str, dict[str, Any]] = {}
    for name in dir(cls):
        if name.startswith("_") or name not in cls.__dict__:
            continue
        attr = inspect.getattr_static(cls, name)
        if isinstance(attr, property):
            members[name] = {"kind": "property", "params": _method_params(attr.fget)}
        elif isinstance(attr, (classmethod, staticmethod)):
            members[name] = {"kind": "function", "params": _method_params(attr.__func__)}
        elif inspect.isfunction(attr):
            members[name] = {"kind": "function", "params": _method_params(attr)}
        else:
            # Data attributes, nested classes and non-function descriptors
            # (e.g. Qt signals): record a stable representation of the value.
            if callable(attr) and not isinstance(attr, type):
                attr = f"<{type(attr).__module__}.{type(attr).__qualname__}>"
            members[name] = {"kind": "constant", "value": _canonical_value(attr)}
    return members


def _serialize_item(name: str, members: bool, module_root: str) -> dict[str, Any]:
    """Serialize one reference item to its snapshot representation."""
    obj, parent = _resolve_item(name, module_root)
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return {"kind": "enum", "members": sorted(m.name for m in obj)}
        data: dict[str, Any] = {"kind": "class", "init": _class_init_params(obj)}
        if members:
            data["members"] = _class_members(obj)
        return data
    if isinstance(obj, property):
        return {"kind": "property", "params": _method_params(obj.fget)}
    if callable(obj):
        params = _method_params(obj) if isinstance(parent, type) else _signature(obj)
        return {"kind": "function", "params": params}
    return {"kind": "constant", "value": _canonical_value(obj)}


def _current_api() -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Serialize the current API; return (snapshot, resolution errors)."""
    module_root, reference = _load_reference()
    current: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for name, members in reference.items():
        try:
            current[name] = _serialize_item(name, members, module_root)
        except Exception as exc:
            errors.append(f"{name}: cannot be imported or inspected: {exc!r}")
    return current, errors


def _compare_positional(
    old_pos: list[dict[str, str | None]],
    new_pos: list[dict[str, str | None]],
    ctx: str,
    breaking: list[str],
    notes: list[str],
) -> None:
    """Compare the positional parameter blocks, slot by slot."""
    for i, old_p in enumerate(old_pos):
        if i >= len(new_pos):
            breaking.append(
                f"{ctx}: positional parameter '{old_p['name']}' was removed "
                "or moved past a new '*'"
            )
            continue
        new_p = new_pos[i]
        if new_p["name"] != old_p["name"]:
            breaking.append(
                f"{ctx}: positional parameter '{old_p['name']}' was renamed "
                f"to '{new_p['name']}' or reordered"
            )
            continue
        _compare_matched(old_p, new_p, ctx, breaking, notes)
    for new_p in new_pos[len(old_pos) :]:
        if new_p["default"] is None:
            breaking.append(f"{ctx}: new required positional parameter '{new_p['name']}'")
        else:
            notes.append(f"{ctx}: new optional positional parameter '{new_p['name']}'")


def _check_lost_keyword_only(
    old: list[dict[str, str | None]],
    new: list[dict[str, str | None]],
    ctx: str,
    breaking: list[str],
    notes: list[str],
) -> None:
    """Check that no keyword-only parameter was removed or restricted."""
    old_kw = {p["name"]: p for p in old if p["kind"] == "keyword_only"}
    new_kw = {p["name"]: p for p in new if p["kind"] == "keyword_only"}
    new_pos_names = {p["name"] for p in new if p["kind"] in _POSITIONAL_KINDS}
    for name, old_p in old_kw.items():
        if name in new_kw:
            _compare_matched(old_p, new_kw[name], ctx, breaking, notes)
        elif name in new_pos_names:
            notes.append(f"{ctx}: keyword-only parameter '{name}' is now positional-callable")
        else:
            breaking.append(f"{ctx}: keyword-only parameter '{name}' was removed")


def _check_new_keyword_only(
    old: list[dict[str, str | None]],
    new: list[dict[str, str | None]],
    ctx: str,
    breaking: list[str],
    notes: list[str],
) -> None:
    """Check that new keyword-only parameters are optional."""
    old_kw = {p["name"]: p for p in old if p["kind"] == "keyword_only"}
    new_kw = {p["name"]: p for p in new if p["kind"] == "keyword_only"}
    old_pos_names = {p["name"] for p in old if p["kind"] in _POSITIONAL_KINDS}
    for name, new_p in new_kw.items():
        if name in old_kw or name in old_pos_names:
            continue
        if new_p["default"] is None:
            breaking.append(f"{ctx}: new required keyword-only parameter '{name}'")
        else:
            notes.append(f"{ctx}: new optional keyword-only parameter '{name}'")


def _compare_keyword_only(
    old: list[dict[str, str | None]],
    new: list[dict[str, str | None]],
    ctx: str,
    breaking: list[str],
    notes: list[str],
) -> None:
    """Compare keyword-only parameters by name."""
    _check_lost_keyword_only(old, new, ctx, breaking, notes)
    _check_new_keyword_only(old, new, ctx, breaking, notes)


def _compare_var_params(
    old: list[dict[str, str | None]],
    new: list[dict[str, str | None]],
    ctx: str,
    breaking: list[str],
    notes: list[str],
) -> None:
    """Compare the presence of *args and **kwargs."""
    for var_kind, label in (("var_positional", "*args"), ("var_keyword", "**kwargs")):
        had = any(p["kind"] == var_kind for p in old)
        has = any(p["kind"] == var_kind for p in new)
        if had and not has:
            breaking.append(f"{ctx}: '{label}' was removed")
        elif has and not had:
            notes.append(f"{ctx}: '{label}' was added")


def _compare_params(
    old: list[dict[str, str | None]],
    new: list[dict[str, str | None]],
    ctx: str,
) -> tuple[list[str], list[str]]:
    """
    Compare two parameter lists for backwards compatibility.

    Returns
    -------
    tuple[list[str], list[str]]
        (breaking changes, non-breaking notes), each a list of messages.
    """
    breaking: list[str] = []
    notes: list[str] = []
    old_pos = [p for p in old if p["kind"] in _POSITIONAL_KINDS]
    new_pos = [p for p in new if p["kind"] in _POSITIONAL_KINDS]
    _compare_positional(old_pos, new_pos, ctx, breaking, notes)
    _compare_keyword_only(old, new, ctx, breaking, notes)
    _compare_var_params(old, new, ctx, breaking, notes)
    return breaking, notes


def _compare_matched(
    old_p: dict[str, str | None],
    new_p: dict[str, str | None],
    ctx: str,
    breaking: list[str],
    notes: list[str],
) -> None:
    """Compare two parameters that are known to share a name and slot."""
    name = old_p["name"]
    if old_p["default"] is None and new_p["default"] is not None:
        notes.append(f"{ctx}: parameter '{name}' is now optional (default {new_p['default']})")
    elif old_p["default"] is not None and new_p["default"] is None:
        breaking.append(f"{ctx}: parameter '{name}' is now required")
    elif old_p["default"] != new_p["default"]:
        breaking.append(
            f"{ctx}: default of parameter '{name}' changed: "
            f"{old_p['default']} -> {new_p['default']}"
        )
    if old_p["kind"] != new_p["kind"]:
        if (old_p["kind"], new_p["kind"]) in _RELAXING_KIND_CHANGES:
            notes.append(
                f"{ctx}: parameter '{name}' kind relaxed ({old_p['kind']} -> {new_p['kind']})"
            )
        else:
            breaking.append(
                f"{ctx}: parameter '{name}' kind restricted ({old_p['kind']} -> {new_p['kind']})"
            )
    if old_p["annotation"] != new_p["annotation"]:
        notes.append(f"{ctx}: annotation of parameter '{name}' changed")


def _compare_member(
    old_m: dict[str, Any],
    new_m: dict[str, Any],
    ctx: str,
) -> tuple[list[str], list[str]]:
    """Compare two class members of the same name."""
    if old_m["kind"] != new_m["kind"]:
        return [f"{ctx}: kind changed ({old_m['kind']} -> {new_m['kind']})"], []
    if old_m["kind"] == "constant":
        if old_m["value"] != new_m["value"]:
            return [f"{ctx}: value changed"], []
        return [], []
    return _compare_params(old_m["params"], new_m["params"], ctx)


def _compare_enum(
    key: str,
    old_members: list[str],
    new_members: list[str],
) -> tuple[list[str], list[str]]:
    """Compare enum member names: removals break, additions note."""
    breaking = [
        f"{key}: enum member '{m}' removed" for m in sorted(set(old_members) - set(new_members))
    ]
    notes = [
        f"{key}: enum member '{m}' added" for m in sorted(set(new_members) - set(old_members))
    ]
    return breaking, notes


def _compare_class(
    key: str,
    old_item: dict[str, Any],
    new_item: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Compare a class constructor and its own public members."""
    breaking, notes = _compare_params(old_item["init"], new_item["init"], f"{key}.__init__")
    old_members = old_item.get("members", {})
    new_members = new_item.get("members", {})
    for member in old_members:
        if member not in new_members:
            breaking.append(f"{key}.{member}: member removed")
            continue
        b, n = _compare_member(old_members[member], new_members[member], f"{key}.{member}")
        breaking.extend(b)
        notes.extend(n)
    for member in new_members:
        if member not in old_members:
            notes.append(f"{key}.{member}: new member")
    return breaking, notes


def _compare_item(
    key: str,
    old_item: dict[str, Any],
    new_item: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Compare two snapshot items of the same name, dispatching on kind."""
    if old_item["kind"] != new_item["kind"]:
        return [f"{key}: kind changed ({old_item['kind']} -> {new_item['kind']})"], []
    kind = old_item["kind"]
    if kind == "constant":
        if old_item["value"] != new_item["value"]:
            return [f"{key}: value changed"], []
        return [], []
    if kind == "enum":
        return _compare_enum(key, old_item["members"], new_item["members"])
    if kind in ("function", "property"):
        return _compare_params(old_item["params"], new_item["params"], key)
    return _compare_class(key, old_item, new_item)


def _compare_items(
    old: dict[str, dict[str, Any]],
    new: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Compare two API snapshots; return (breaking changes, notes)."""
    breaking = [f"{key}: removed from the supported API" for key in old if key not in new]
    notes = [f"{key}: newly listed in the supported API" for key in new if key not in old]
    for key in sorted(set(old) & set(new)):
        b, n = _compare_item(key, old[key], new[key])
        breaking.extend(b)
        notes.extend(n)
    return breaking, notes


def _dump_inline_param(param: dict[str, Any]) -> str:
    """Serialize one parameter as a single JSON line, omitting nulls."""
    return json.dumps({k: v for k, v in sorted(param.items()) if v is not None})


def _dump_dict(value: dict[str, Any], indent: int) -> str:
    """Serialize a mapping with sorted keys, omitting null values."""
    if not value:
        return "{}"
    pad = "  " * indent
    child_pad = "  " * (indent + 1)
    lines = []
    for key in sorted(value):
        item = value[key]
        if item is None:
            continue
        if isinstance(item, (dict, list)) and item:
            lines.append(f'{child_pad}"{key}": {_dump_value(item, indent + 1)}')
        else:
            lines.append(f'{child_pad}"{key}": {json.dumps(item)}')
    return "{\n" + ",\n".join(lines) + "\n" + pad + "}"


def _dump_list(value: list[Any], indent: int) -> str:
    """Serialize a list: one line per parameter dict, else inline."""
    if not value:
        return "[]"
    pad = "  " * indent
    child_pad = "  " * (indent + 1)
    if all(isinstance(x, dict) for x in value):
        inner = ",\n".join(child_pad + _dump_inline_param(x) for x in value)
        return "[\n" + inner + "\n" + pad + "]"
    return "[" + ", ".join(json.dumps(x) for x in value) + "]"


def _dump_value(value: Any, indent: int) -> str:
    """Serialize a snapshot value: one line per parameter, nulls omitted."""
    if isinstance(value, dict):
        return _dump_dict(value, indent)
    if isinstance(value, list):
        return _dump_list(value, indent)
    return json.dumps(value)


def _dump_snapshot(data: dict[str, dict[str, Any]]) -> str:
    """Serialize the full snapshot for storage (still plain JSON)."""
    return _dump_value(data, 0) + "\n"


def _normalize_params(value: Any) -> None:
    """Restore null 'default'/'annotation' keys omitted by the compact format."""
    if isinstance(value, dict):
        if "name" in value and "kind" in value:
            value.setdefault("default", None)
            value.setdefault("annotation", None)
        for item in value.values():
            _normalize_params(item)
    elif isinstance(value, list):
        for item in value:
            _normalize_params(item)


def _load_snapshot() -> dict[str, dict[str, Any]] | None:
    """Load and normalize the stored snapshot, or None if it is missing."""
    if not SNAPSHOT_FILE.exists():
        return None
    data: dict[str, dict[str, Any]] = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    _normalize_params(data)
    return data


def test_public_api_stability() -> None:
    """
    Test that the supported API only changed in backwards-compatible ways.

    The current API (from great-docs.yml) is compared against the stored
    snapshot. Breaking changes fail the test; non-breaking changes are
    reported and require a snapshot regeneration.
    """
    update = os.environ.get(UPDATE_ENV) == "1"
    current, errors = _current_api()
    if errors:
        pytest.fail("Reference items of great-docs.yml cannot be resolved:\n" + "\n".join(errors))

    snapshot = _load_snapshot()
    if snapshot is None and not update:
        pytest.fail(
            "API snapshot is missing; generate it with "
            f"`{UPDATE_ENV}=1 uv run pytest tests/test_public_api.py` "
            "and commit the result."
        )

    breaking, notes = _compare_items(snapshot or {}, current)
    if update:
        SNAPSHOT_FILE.write_text(_dump_snapshot(current), encoding="utf-8")
        print(f"API snapshot written to {SNAPSHOT_FILE}")

    if breaking:
        message = "Breaking changes to the supported API:\n" + "\n".join(breaking)
        if notes:
            message += "\n\nNon-breaking changes:\n" + "\n".join(notes)
        message += (
            "\n\nIf this change is intentional and went through the "
            "deprecation cycle, regenerate the snapshot with "
            f"`{UPDATE_ENV}=1 uv run pytest tests/test_public_api.py`."
        )
        pytest.fail(message)
    if notes:
        print("Non-breaking API changes (regenerate the snapshot to silence):")
        for note in notes:
            print(f"  - {note}")

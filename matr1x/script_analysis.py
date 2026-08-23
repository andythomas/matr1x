# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Conservative static analysis for matrix-script measurement totals."""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, TypeGuard


@dataclass(frozen=True)
class PointCounts:
    """Statically inferred measurement totals for a matrix-script source."""

    initial: int | None
    datafiles: dict[int, int | None]

    def for_call_lines(self, lines: list[int]) -> int | None:
        """Return the total for the nearest active initialization call.

        Parameters
        ----------
        lines : list of int
            Active user-source lines, from innermost to outermost.

        Returns
        -------
        int or None
            The inferred total, or None if it cannot be determined.
        """
        for line in lines:
            if line in self.datafiles:
                return self.datafiles[line]
        return self.initial


@dataclass(frozen=True)
class _Sequence:
    """A symbolic sequence known only by its length."""

    length: int


@dataclass(frozen=True)
class _Unknown:
    """A value that cannot be resolved without running user code."""


_UNKNOWN: Final = _Unknown()
_MAX_REPEATED_INITIALIZATIONS: Final = 10_000
_SymbolicValue = int | float | bool | _Sequence | _Unknown
_Numeric = int | float
_NumericOperation = Callable[[_Numeric, _Numeric], _Numeric]
_ComparisonOperation = Callable[[_Numeric, _Numeric], bool]
_NUMERIC_OPERATIONS: Final[dict[type[ast.operator], _NumericOperation]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_COMPARISON_OPERATIONS: Final[dict[type[ast.cmpop], _ComparisonOperation]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


@dataclass
class _CounterState:
    """Track measurements collected under the currently active datafile."""

    active_line: int | None = None
    active_count: int = 0
    initial_counts: set[int] = field(default_factory=set)
    datafile_counts: dict[int, set[int]] = field(default_factory=dict)
    unknown: bool = False

    def measure(self) -> None:
        """Record one statically known measurement."""
        self.active_count += 1

    def initialize(self, line: int) -> None:
        """Start a new datafile segment at *line*."""
        self.finish_active()
        self.active_line = line
        self.active_count = 0

    def finish_active(self) -> None:
        """Store the total for the current datafile segment."""
        if self.active_line is None:
            self.initial_counts.add(self.active_count)
        else:
            self.datafile_counts.setdefault(self.active_line, set()).add(self.active_count)

    def add_measurements(self, count: int) -> None:
        """Record *count* measurements without expanding a loop."""
        self.active_count += count

    def mark_unknown(self) -> None:
        """Mark the complete result unknown after dynamic measurement flow."""
        self.unknown = True

    def result(self) -> PointCounts:
        """Build the immutable public analysis result."""
        self.finish_active()
        if self.unknown:
            return PointCounts(None, {line: None for line in self.datafile_counts})

        initial = _single_count(self.initial_counts)
        datafiles = {line: _single_count(counts) for line, counts in self.datafile_counts.items()}
        return PointCounts(initial, datafiles)


def _single_count(counts: set[int]) -> int | None:
    """Return the single count in *counts*, otherwise None."""
    return next(iter(counts)) if len(counts) == 1 else None


class _Analyzer:
    """Evaluate the statically safe subset of matrix-script Python."""

    def __init__(self, tree: ast.Module):
        self.tree = tree
        self.functions: dict[str, ast.FunctionDef] = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        self.numpy_modules: set[str] = {"numpy"}
        self.numpy_functions: set[str] = set()
        self.call_stack: set[str] = set()
        self.redefined_api: set[str] = set()
        self.state = _CounterState()

    def analyze(self) -> PointCounts:
        """Analyze the module and return exact totals when provable."""
        self._execute_block(self.tree.body, {})
        return self.state.result()

    def _execute_block(self, statements: list[ast.stmt], env: dict[str, _SymbolicValue]) -> None:
        for statement in statements:
            if self.state.unknown:
                return
            self._execute_statement(statement, env)

    def _execute_statement(self, statement: ast.stmt, env: dict[str, _SymbolicValue]) -> None:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            self._record_import(statement)
        elif isinstance(statement, ast.Assign):
            self._record_api_rebindings(statement.targets)
            self._assign(statement.targets, self._evaluate(statement.value, env), env)
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            self._record_api_rebindings([statement.target])
            self._assign([statement.target], self._evaluate(statement.value, env), env)
        elif isinstance(statement, ast.Expr):
            self._evaluate(statement.value, env)
        elif isinstance(statement, ast.If):
            self._execute_if(statement, env)
        elif isinstance(statement, ast.For):
            self._execute_for(statement, env)
        elif isinstance(statement, ast.While):
            self._execute_while(statement, env)
        elif isinstance(statement, ast.FunctionDef):
            if statement.name in {"measure_system", "init_datafile"}:
                self.redefined_api.add(statement.name)
        elif isinstance(statement, ast.Raise) or self._contains_effect([statement]):
            self.state.mark_unknown()

    def _record_import(self, statement: ast.Import | ast.ImportFrom) -> None:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name == "numpy":
                    self.numpy_modules.add(alias.asname or "numpy")
            return
        if statement.module == "numpy":
            self.numpy_functions.update(alias.asname or alias.name for alias in statement.names)

    def _assign(
        self,
        targets: list[ast.expr],
        value: _SymbolicValue,
        env: dict[str, _SymbolicValue],
    ) -> None:
        for target in targets:
            if isinstance(target, ast.Name):
                env[target.id] = value

    def _record_api_rebindings(self, targets: list[ast.expr]) -> None:
        """Record assignments that replace matrix-script entry points."""
        for target in targets:
            if isinstance(target, ast.Name) and target.id in {"measure_system", "init_datafile"}:
                self.redefined_api.add(target.id)

    def _execute_if(self, statement: ast.If, env: dict[str, _SymbolicValue]) -> None:
        condition = self._evaluate(statement.test, env)
        if isinstance(condition, bool):
            self._execute_block(statement.body if condition else statement.orelse, env)
        elif self._contains_effect(statement.body + statement.orelse) or self._contains_raise(
            statement.body + statement.orelse
        ):
            self.state.mark_unknown()

    def _execute_for(self, statement: ast.For, env: dict[str, _SymbolicValue]) -> None:
        iterable = self._evaluate(statement.iter, env)
        if not isinstance(iterable, _Sequence):
            if self._contains_effect(statement.body):
                self.state.mark_unknown()
            return
        if iterable.length == 0:
            self._execute_block(statement.orelse, env)
            return
        has_initialization = self._contains_initialization(statement.body)
        if self._contains_loop_exit(statement.body) and self._contains_effect(statement.body):
            self.state.mark_unknown()
        elif has_initialization:
            self._execute_repeated_initialization_loop(statement, iterable.length, env)
        elif self._has_assignment(statement.body) and self._contains_effect(statement.body):
            self.state.mark_unknown()
        else:
            self._execute_counted_loop(statement, iterable.length, env)
        if not self.state.unknown:
            self._execute_block(statement.orelse, env)

    def _execute_counted_loop(
        self, statement: ast.For, repetitions: int, env: dict[str, _SymbolicValue]
    ) -> None:
        before = self.state.active_count
        loop_env = dict(env)
        self._assign([statement.target], _UNKNOWN, loop_env)
        self._execute_block(statement.body, loop_env)
        if self.state.unknown:
            return
        measured = self.state.active_count - before
        self.state.active_count = before
        self.state.add_measurements(measured * repetitions)
        self._assign([statement.target], _UNKNOWN, env)

    def _execute_repeated_initialization_loop(
        self, statement: ast.For, repetitions: int, env: dict[str, _SymbolicValue]
    ) -> None:
        if repetitions > _MAX_REPEATED_INITIALIZATIONS:
            self.state.mark_unknown()
            return
        for _ in range(repetitions):
            loop_env = dict(env)
            self._assign([statement.target], _UNKNOWN, loop_env)
            self._execute_block(statement.body, loop_env)
            if self.state.unknown:
                return
        self._assign([statement.target], _UNKNOWN, env)

    def _execute_while(self, statement: ast.While, env: dict[str, _SymbolicValue]) -> None:
        condition = self._evaluate(statement.test, env)
        if condition is False:
            self._execute_block(statement.orelse, env)
        elif self._contains_effect(statement.body + statement.orelse):
            self.state.mark_unknown()

    def _evaluate(self, expression: ast.expr, env: dict[str, _SymbolicValue]) -> _SymbolicValue:
        if isinstance(expression, ast.Constant) and isinstance(
            expression.value, (int, float, bool)
        ):
            return expression.value
        if isinstance(expression, ast.Name):
            return env.get(expression.id, _UNKNOWN)
        if isinstance(expression, (ast.List, ast.Tuple)):
            for element in expression.elts:
                self._evaluate(element, env)
            return _Sequence(len(expression.elts))
        if isinstance(expression, ast.UnaryOp):
            return self._evaluate_unary(expression, env)
        if isinstance(expression, ast.BinOp):
            return self._evaluate_binary(expression, env)
        if isinstance(expression, ast.Compare):
            return self._evaluate_compare(expression, env)
        if isinstance(expression, ast.BoolOp):
            return self._evaluate_bool_op(expression, env)
        if isinstance(expression, ast.Call):
            return self._evaluate_call(expression, env)
        if self._expression_contains_api_call(expression):
            self.state.mark_unknown()
        return _UNKNOWN

    def _evaluate_unary(
        self, expression: ast.UnaryOp, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        operand = self._evaluate(expression.operand, env)
        if not isinstance(operand, (int, float, bool)):
            return _UNKNOWN
        if isinstance(expression.op, ast.USub):
            return -operand
        if isinstance(expression.op, ast.UAdd):
            return +operand
        if isinstance(expression.op, ast.Not):
            return not operand
        return _UNKNOWN

    def _evaluate_binary(
        self, expression: ast.BinOp, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        left = self._evaluate(expression.left, env)
        right = self._evaluate(expression.right, env)
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return _UNKNOWN
        operation = _NUMERIC_OPERATIONS.get(type(expression.op))
        if operation is None:
            return _UNKNOWN
        try:
            return operation(left, right)
        except (ArithmeticError, ValueError):
            return _UNKNOWN

    def _evaluate_compare(
        self, expression: ast.Compare, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        if len(expression.ops) != 1 or len(expression.comparators) != 1:
            return _UNKNOWN
        left = self._evaluate(expression.left, env)
        right = self._evaluate(expression.comparators[0], env)
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return _UNKNOWN
        operation = _COMPARISON_OPERATIONS.get(type(expression.ops[0]))
        return operation(left, right) if operation is not None else _UNKNOWN

    def _evaluate_bool_op(
        self, expression: ast.BoolOp, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        values = [self._evaluate(value, env) for value in expression.values]
        if not all(isinstance(value, bool) for value in values):
            return _UNKNOWN
        return all(values) if isinstance(expression.op, ast.And) else any(values)

    def _evaluate_call(
        self, expression: ast.Call, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        name = _call_name(expression.func)
        if name == "measure_system":
            if name in self.redefined_api:
                self.state.mark_unknown()
                return _UNKNOWN
            self.state.measure()
            return _UNKNOWN
        if name == "init_datafile":
            if name in self.redefined_api:
                self.state.mark_unknown()
                return _UNKNOWN
            self.state.initialize(expression.lineno)
            return _UNKNOWN
        if name == "range":
            return self._evaluate_range(expression, env)
        if self._is_numpy_call(expression, "linspace"):
            return self._evaluate_linspace(expression, env)
        if self._is_numpy_call(expression, "arange"):
            return self._evaluate_arange(expression, env)
        if name in self.functions:
            return self._execute_function(name, expression, env)
        for argument in expression.args:
            self._evaluate(argument, env)
        for keyword in expression.keywords:
            self._evaluate(keyword.value, env)
        return _UNKNOWN

    def _evaluate_range(
        self, expression: ast.Call, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        arguments = [self._evaluate(argument, env) for argument in expression.args]
        length = _range_length(arguments)
        return _Sequence(length) if length is not None else _UNKNOWN

    def _evaluate_linspace(
        self, expression: ast.Call, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        if len(expression.args) >= 3:
            points = self._evaluate(expression.args[2], env)
        else:
            points = self._keyword_value(expression, "num", env, 50)
        return _Sequence(points) if _is_nonnegative_int(points) else _UNKNOWN

    def _evaluate_arange(
        self, expression: ast.Call, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        arguments = [self._evaluate(argument, env) for argument in expression.args]
        length = _range_length(arguments)
        return _Sequence(length) if length is not None else _UNKNOWN

    def _keyword_value(
        self, expression: ast.Call, name: str, env: dict[str, _SymbolicValue], default: int
    ) -> _SymbolicValue:
        for keyword in expression.keywords:
            if keyword.arg == name:
                return self._evaluate(keyword.value, env)
        return default

    def _is_numpy_call(self, expression: ast.Call, function: str) -> bool:
        if isinstance(expression.func, ast.Name):
            return expression.func.id == function and function in self.numpy_functions
        return (
            isinstance(expression.func, ast.Attribute)
            and expression.func.attr == function
            and isinstance(expression.func.value, ast.Name)
            and expression.func.value.id in self.numpy_modules
        )

    def _execute_function(
        self, name: str, expression: ast.Call, env: dict[str, _SymbolicValue]
    ) -> _SymbolicValue:
        if name in self.call_stack:
            self.state.mark_unknown()
            return _UNKNOWN
        function = self.functions[name]
        if self._contains_raise(function.body) or (
            self._contains_return(function.body) and self._contains_effect(function.body)
        ):
            self.state.mark_unknown()
            return _UNKNOWN
        if expression.keywords or len(expression.args) > len(function.args.args):
            self.state.mark_unknown()
            return _UNKNOWN
        arguments = [self._evaluate(argument, env) for argument in expression.args]
        parameters = function.args.args
        if len(arguments) < len(parameters) - len(function.args.defaults):
            self.state.mark_unknown()
            return _UNKNOWN
        local_env = dict(env)
        defaults = [self._evaluate(default, env) for default in function.args.defaults]
        missing = len(parameters) - len(arguments)
        values = arguments + defaults[len(defaults) - missing :]
        if any(isinstance(value, _Unknown) for value in values):
            self.state.mark_unknown()
            return _UNKNOWN
        local_env.update({parameter.arg: value for parameter, value in zip(parameters, values)})
        self.call_stack.add(name)
        self._execute_block(function.body, local_env)
        self.call_stack.remove(name)
        return _UNKNOWN

    def _contains_effect(self, statements: list[ast.stmt]) -> bool:
        return self._contains_call(statements, {"measure_system", "init_datafile"}, set())

    def _contains_initialization(self, statements: list[ast.stmt]) -> bool:
        return self._contains_call(statements, {"init_datafile"}, set())

    def _contains_loop_exit(self, statements: list[ast.stmt]) -> bool:
        """Return whether a loop body can break or skip an iteration."""
        return self._contains_node(statements, (ast.Break, ast.Continue))

    def _contains_return(self, statements: list[ast.stmt]) -> bool:
        """Return whether a function body can return early."""
        return self._contains_node(statements, (ast.Return,))

    def _contains_raise(self, statements: list[ast.stmt]) -> bool:
        """Return whether a statement block can raise an exception."""
        return self._contains_node(statements, (ast.Raise,))

    def _has_assignment(self, statements: list[ast.stmt]) -> bool:
        """Return whether *statements* can carry state between iterations."""
        return any(
            isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr))
            for statement in statements
            for node in ast.walk(statement)
        )

    def _expression_contains_api_call(self, expression: ast.expr) -> bool:
        """Return whether an unsupported expression invokes a matrix API."""
        return any(
            _call_name(node.func) in {"measure_system", "init_datafile"}
            for node in ast.walk(expression)
            if isinstance(node, ast.Call)
        )

    def _contains_node(
        self, statements: list[ast.stmt], node_types: tuple[type[ast.stmt], ...]
    ) -> bool:
        """Return whether a statement block contains one of *node_types*."""
        return any(
            isinstance(node, node_types)
            for statement in statements
            for node in ast.walk(statement)
        )

    def _contains_call(
        self, statements: list[ast.stmt], targets: set[str], visited: set[str]
    ) -> bool:
        for statement in statements:
            if self._statement_contains_call(statement, targets, visited):
                return True
        return False

    def _statement_contains_call(
        self, statement: ast.stmt, targets: set[str], visited: set[str]
    ) -> bool:
        """Return whether *statement* directly or indirectly calls a target."""
        for call in (node for node in ast.walk(statement) if isinstance(node, ast.Call)):
            if self._call_targets_effect(call, targets, visited):
                return True
        return False

    def _call_targets_effect(self, call: ast.Call, targets: set[str], visited: set[str]) -> bool:
        """Return whether *call* can reach one of *targets*."""
        name = _call_name(call.func)
        if name in targets:
            return True
        if name not in self.functions or name in visited:
            return False
        return self._contains_call(self.functions[name].body, targets, visited | {name})


def _call_name(function: ast.expr) -> str | None:
    """Return the directly called name, excluding aliases and attributes."""
    return function.id if isinstance(function, ast.Name) else None


def _range_length(arguments: list[_SymbolicValue]) -> int | None:
    """Return the exact length of a supported ``range`` call."""
    if not 1 <= len(arguments) <= 3:
        return None
    integers = [value for value in arguments if _is_int(value)]
    if len(integers) != len(arguments):
        return None
    try:
        if len(integers) == 1:
            return len(range(integers[0]))
        if len(integers) == 2:
            return len(range(integers[0], integers[1]))
        return len(range(integers[0], integers[1], integers[2]))
    except ValueError:
        return None


def _is_int(value: _SymbolicValue) -> TypeGuard[int]:
    """Return whether *value* is an integer but not a boolean."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_nonnegative_int(value: _SymbolicValue) -> TypeGuard[int]:
    """Return whether *value* is a nonnegative integer."""
    return _is_int(value) and value >= 0


def infer_point_counts(source: str) -> PointCounts:
    """Infer exact per-datafile ``measure_system`` totals from source.

    The analyzer interprets only a deliberately restricted, side-effect-free
    Python subset. It returns unknown totals whenever user code could change
    the measurement count at runtime.

    Parameters
    ----------
    source : str
        The user-authored matrix-script source.

    Returns
    -------
    PointCounts
        Exact totals where they can be proven, otherwise None.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return PointCounts(None, {})
    return _Analyzer(tree).analyze()

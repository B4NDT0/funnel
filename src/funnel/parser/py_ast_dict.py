import math
from datetime import datetime, time
from functools import lru_cache
from typing import Any, Callable, Iterable, Mapping, Sequence

from parser import FilterParser


# -------- dotted-path accessor --------
def _get_path(row: Any, path: str, *, allow_private: bool = False) -> Any:
    cur = row
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(part, None)
            continue
        if isinstance(cur, (list, tuple)):
            try:
                idx = int(part)
            except ValueError:
                return None
            return cur[idx] if 0 <= idx < len(cur) else None
        if not allow_private and part.startswith("_"):
            return None
        cur = getattr(cur, part, None)
    return cur


# -------- primitives / lifted ops --------
_to_str = lambda x: "" if x is None else str(x)


def _contains(a: Any, b: Any) -> bool:
    if isinstance(a, str):
        return _to_str(b) in a
    if isinstance(a, Mapping):
        return b in a
    try:
        return b in a
    except TypeError:
        return False


def _in_list(a: Any, seq: Sequence[Any]) -> bool:
    try:
        return a in seq
    except TypeError:
        sseq = list(map(_to_str, seq))
        return _to_str(a) in sseq


_length = lambda x: (len(x) if hasattr(x, "__len__") else 0)
_indexOf = lambda s, sub: _to_str(s).find(_to_str(sub))
_replace = lambda s, old, new: _to_str(s).replace(_to_str(old), _to_str(new))
_substring = lambda s, start, length=None: (_to_str(s)[start:] if length is None else _to_str(s)[start:start + length])
_toLower = lambda s: _to_str(s).lower()
_toUpper = lambda s: _to_str(s).upper()
_trim = lambda s: _to_str(s).strip()


def _numop(fn: Callable[[float], int]):
    def inner(x: Any) -> int:
        try:
            return fn(float(x))
        except Exception:
            return 0

    return inner


_round, _floor, _ceiling = _numop(round), _numop(math.floor), _numop(math.ceil)
_dt = lambda name: (lambda dt: getattr(dt, name, 0) or 0)

_as_fn = lambda x: (x if callable(x) else (lambda _row, _x=x: _x))


def _lift1(op):  # unary
    def gen(a):
        A = _as_fn(a)
        return lambda row: op(A(row))

    return gen


def _lift2(op):  # binary
    def gen(a, b):
        A, B = _as_fn(a), _as_fn(b)
        return lambda row: op(A(row), B(row))

    return gen


def _lift3(op):  # ternary
    def gen(a, b, c):
        A, B, C = _as_fn(a), _as_fn(b), _as_fn(c)
        return lambda row: op(A(row), B(row), C(row))

    return gen


def _nary_bool(combiner):
    def gen(*args):
        Fs = [_as_fn(a) for a in args]
        return lambda row: combiner(bool(f(row)) for f in Fs)

    return gen


# -------- concrete FilterParser --------
class _PythonFilterParser(FilterParser):
    # base funcs
    func_map = {
        'length': _lift1(_length),
        'indexof': _lift2(_indexOf),
        'replace': _lift3(_replace),
        'substring': lambda s, start, length=None: (
            _lift3(_substring)(s, start, length)
            if length is not None else
            _lift2(lambda a, b: _substring(a, b, None))(s, start)
        ),
        'tolower': _lift1(_toLower),
        'toupper': _lift1(_toUpper),
        'trim': _lift1(_trim),
        'round': _lift1(_round),
        'floor': _lift1(_floor),
        'ceiling': _lift1(_ceiling),
    }
    # add datetime parts succinctly
    func_map |= {k: _lift1(_dt(k)) for k in "year month day hour minute second".split()}

    # helpers to reduce repetition
    _nz = lambda a, d: (a if a is not None else d)
    _cmp = lambda op: _lift2(lambda a, b: (a is not None and b is not None and op(a, b)))

    op_map = {
        # comparisons
        'eq': _lift2(lambda a, b: a == b),
        'ne': _lift2(lambda a, b: a != b),
        'gt': _cmp(lambda a, b: a > b),
        'lt': _cmp(lambda a, b: a < b),
        'ge': _cmp(lambda a, b: a >= b),
        'le': _cmp(lambda a, b: a <= b),
        # arithmetic
        'add': _lift2(lambda a, b: (a or 0) + (b or 0)),
        'sub': _lift2(lambda a, b: (a or 0) - (b or 0)),
        'mul': _lift2(lambda a, b: (a or 0) * (b or 0)),
        'div': _lift2(lambda a, b: (a or 0) / (b or 1)),
        'mod': _lift2(lambda a, b: (a or 0) % (b or 1)),
        # logical (n-ary)
        'AND': _nary_bool(all),
        'OR': _nary_bool(any),
        # string-like
        'like': _lift2(lambda a, b: _to_str(b) in _to_str(a)),
        'endswith': _lift2(lambda a, b: _to_str(a).endswith(_to_str(b))),
        'startswith': _lift2(lambda a, b: _to_str(a).startswith(_to_str(b))),
        # containment / membership
        'contains': _lift2(_contains),
        'lacks': _lift2(lambda a, b: not _contains(a, b)),
        'in': _lift2(lambda a, b: _in_list(a, b if isinstance(b, (list, tuple, set)) else [b])),
    }
    # aliases
    op_map['has'] = op_map['contains']
    op_map['hasNot'] = op_map['lacks']

    def __init__(self):
        super().__init__(op_map=self.op_map, func_map=self.func_map)

    def get_column(self, col: str):
        name = col.strip()
        return lambda row, _n=name: _get_path(row, _n)


# -------- public API --------
class DSLParseError(ValueError): ...


class DSLSemanticError(ValueError): ...


class DictASTFilterParser:
    def __init__(self) -> None:
        self._parser = _PythonFilterParser()
        extra_literal_parsers = [
            (r"^'?\d{2,4}-\d{1,2}-\d{1,2}'?$", lambda s: datetime.strptime(s.strip("'"), "%Y-%m-%d")),
            (r"^'?\d{1,2}:\d{1,2}(:\d{1,2})?'?$", lambda s: time.fromisoformat(s.strip("'"))),
            (r"^[+-]?\d+$", lambda s: int(s.strip("'"))),
            (r"^[+-]?\d+\.\d+$", lambda s: float(s.strip("'"))),
            (r"^(?i:true|false)$", lambda s: s.lower() == "true"),
            (r"^'.*'$", lambda s: s.strip("'")),
        ]
        self._parser.parsers = extra_literal_parsers + self._parser.parsers

    @lru_cache(maxsize=256)
    def create_predicate(self, filter_string: str) -> Callable[[Any], bool]:
        try:
            fn_or_val = self._parser.create_filter(filter_string)
        except Exception as e:
            raise DSLParseError(f"DSL parse error: {e}") from e
        fn = fn_or_val if callable(fn_or_val) else (lambda _row, v=fn_or_val: v)

        def pred(row: Any) -> bool:
            try:
                return bool(fn(row))
            except Exception:
                return False

        return pred

    def apply_filter(self, filter_string: str, items: Iterable[Any]) -> list[Any]:
        pred = self.create_predicate(filter_string)
        return [row for row in items if pred(row)]

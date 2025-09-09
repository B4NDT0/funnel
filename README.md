# Funnel

A tiny, backend-agnostic filter engine with one DSL that targets:

* **Python dicts** — compiled to a safe, fast **AST predicate** (`DictASTFilterParser`)
* **MongoDB** — compiled to a Mongo **query dict** (`MongoDbFilterParser`)
* **SQLAlchemy** — compiled to a **WHERE** clause on a `Select` (`SqlAlchemyFilterParser`)

The DSL is intentionally simple (e.g., `field1 gt 5 AND name startswith 'alp'`) and does **not** expose Python syntax. For dicts, we compile to Python AST with a whitelisted runtime—no `eval` on user input.

---

## Features

* Single DSL, multiple targets (dicts, MongoDB, SQLAlchemy)
* Dotted path access: `nested.value`, `tags.0`
* Logical ops: `AND`, `OR`
* Comparisons: `eq ne gt lt ge le`
* String ops: `like startswith endswith`
* Collections: `in` (with list literal), `has` / `contains` / `lacks` / `hasNot`
* String/number/date helpers: `length indexOf replace substring toLower toUpper trim round floor ceiling year month day hour minute second`
* Python 3.12+ (uses modern typing and generics)

---

## Quick start

```bash
# Install uv (if you haven't)
# macOS/Linux:  curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:      irm https://astral.sh/uv/install.ps1 | iex

# From the repo root
uv sync
uv run funnel-demo
```

---

## Usage

### 1) Dicts (AST-compiled predicate)

```python
from funnel.parser.dict_ast import DictASTFilterParser

items = [
    {"field1": 2,  "name": "alpha",     "tags": ["x", "y"]},
    {"field1": 4,  "name": "beta",      "tags": []},
    {"field1": 18, "name": "alphabet",  "tags": ["z"]},
    {"field1": 20, "name": "gamma",     "tags": ["y"]},
    {"field1": 30, "name": "delta",     "nested": {"value": 10}},
]

dsl = "field1 gt 5 AND field1 lt 25"
parser = DictASTFilterParser()

# Filter a list of dicts
print(parser.apply_filter(dsl, items))
# [{'field1': 18, 'name': 'alphabet', 'tags': ['z']},
#  {'field1': 20, 'name': 'gamma', 'tags': ['y']}]

# Or compile once and reuse
pred = parser.create_predicate("name in ['alpha','delta']")
print([row for row in items if pred(row)])
# [{'field1': 2, 'name': 'alpha', 'tags': ['x', 'y']},
#  {'field1': 30, 'name': 'delta', 'nested': {'value': 10}}]
```

### 2) MongoDB

```python
from funnel.parser.mongodb import MongoDbFilterParser
import motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
collection = client["bff"]["calls"]

dsl = "duration gt 20 AND duration lt 100 AND call_id endswith '100'"
query = MongoDbFilterParser().create_filter(dsl)
docs = await collection.find(query).to_list(10)
```

### 3) SQLAlchemy

```python
from sqlalchemy import select
from funnel.parser.sqlalchemy import SqlAlchemyFilterParser
from funnel.actions import Action  # example model

parser = SqlAlchemyFilterParser(Action)
stmt = select(Action)
stmt = parser.add_filter("type eq 'TRANSFER'", stmt)

async with async_session() as session:
    rows = (await session.execute(stmt)).scalars().all()
```

---

## DSL reference

### Literals

* **Strings**: single quotes, escaping with `\'` (`'hello'`)
* **Numbers**: `42`, `3.14`
* **Booleans**: `true`, `false`
* **Lists**: `[1, 2, 3]`, `['a','b']` (used with `in`)
* **Field paths**: `user.name`, `nested.value`, `tags.0`

> Dates/times: for dicts, date functions (e.g., `year(...)`) expect actual `datetime/time` objects in the data. If you need auto-parsing from string literals, extend the grammar (see `dict_ast.py`).

### Operators

| Operator                                | Meaning                                                   |
| --------------------------------------- | --------------------------------------------------------- |
| `eq ne gt lt ge le`                     | comparisons                                               |
| `add sub mul div mod`                   | arithmetic (can be embedded in comparisons)               |
| `AND OR`                                | logical connectives (left-associative)                    |
| `like`                                  | substring match (see case sensitivity note)               |
| `startswith` / `endswith`               | string prefix/suffix                                      |
| `in`                                    | left value is a member of a **list literal** on the right |
| `contains` / `has` / `lacks` / `hasNot` | membership on collection fields (strings/seqs/dicts)      |

**Case sensitivity:**

* MongoDB + SQLAlchemy backends are **case-insensitive** for `like/startswith/endswith`.
* Dict (AST) backend is **case-sensitive** by default. Wrap with `toLower(...)` if you want case-insensitive behavior portably, e.g. `toLower(name) startswith 'alp'`.

### Functions

`length, indexOf, replace, substring, toLower, toUpper, trim, round, floor, ceiling, year, month, day, hour, minute, second`

Examples:

```text
length(name) gt 3
substring(name, 0, 3) eq 'alp'
toLower(name) like 'mm'
year(created_at) ge 2024
```

---

## Design notes (what matters)

* **Safety over `eval`:** dict filtering builds a Python AST and executes in a minimal, whitelisted runtime (see `_ALLOWED_GLOBALS` in `dict_ast.py`).
* **Correct list semantics:** `in` requires a **list literal** on RHS; the parser groups and tags list tokens to avoid pyparsing flattening bugs.
* **Backend differences:** SQLAlchemy uses `ILIKE` and MongoDB uses case-insensitive regex by default for string ops. Dict backend is strict and predictable; normalize explicitly if you need parity.
* **Extensible:** add operators/functions by mapping them to AST calls (dict), Mongo operators, or SQLAlchemy functions.

---

## Installation & environment (uv)

```bash
uv sync                    # create .venv and install deps from pyproject.toml
uv run funnel-demo         # run demo entrypoint
```

Core dependencies:

* `SQLAlchemy`, `asyncpg` (for the SQL backend)
* `motor` (for MongoDB)
* `pyparsing` (DSL grammar)
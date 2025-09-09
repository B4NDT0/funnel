import re
from datetime import datetime, time
from typing import Any, Sequence, Callable, Protocol, TypeVar

import pyparsing as pp

type IDENTIFIER_PARSER_FUNC = Callable[[str], Any]


class QueryGenerator(Protocol):

    def parse_identifier(self, val: str) -> Any:
        pass

    def get_column(self, col: str):
        pass


class FilterParser(QueryGenerator):

    def __init__(self, *,
                 ident_parsers: list[tuple[str, IDENTIFIER_PARSER_FUNC]] | None = None,
                 op_map: dict[str, Callable[..., Any]],
                 func_map: dict[str, Callable[..., Any]]):

        self.parsers = ident_parsers or [
            (r"^'?\d{2,4}-\d{1,2}-\d{1,2}'?$",
             lambda s: datetime.strptime(s.strip("'"), "%Y-%m-%d")),
            (r"^'?\d{1,2}:\d{1,2}(:\d{1,2})?'?",
             lambda s: time.fromisoformat(s.strip("'"))),
            (r"^\d+$",
             lambda s: int(s.strip("'"))),
            (r"^\d+\.\d+$",
             lambda s: float(s.strip("'"))),
            (r"^'.+'$",
             lambda s: s.strip("'")),
            ("true|false",
             lambda s: True if s.lower() == "true" else False),
        ]
        self.func_map = func_map
        self.op_map = op_map

        # Define basic elements
        operator_ = pp.Regex("|".join(self.op_map.keys())).setName("operator")
        number = pp.Regex(r"[\d\.]+")
        identifier = pp.Regex(r"[a-z][\w\.]*")
        str_value = (
                pp.QuotedString("'", unquoteResults=False, escChar="\\")
                | pp.QuotedString('"', unquoteResults=False, escChar="\\")
        )
        date_value = pp.Regex(r"\d{4}-\d{1,2}-\d{1,2}")
        collection_value = pp.Suppress("[") + pp.delimitedList(identifier | str_value) + pp.Suppress("]")
        l_par = pp.Suppress("(")
        r_par = pp.Suppress(")")
        function_call = pp.Forward()
        arg = function_call | identifier | date_value | number | collection_value | str_value
        function_call = pp.Group(identifier + l_par + pp.Optional(pp.delimitedList(arg)) + r_par)
        param = function_call | arg
        condition = pp.Group(param + operator_ + param)

        # Define a full filter expression supporting 'and'/'or'
        self.filter_expression = pp.infixNotation(
            condition,
            [
                ("AND", 2, pp.opAssoc.LEFT),
                ("OR", 2, pp.opAssoc.LEFT),
            ],
        )

    def parse_identifier(self, val: str | pp.ParseResults) -> Any:
        if isinstance(val, str):
            return next((parser(val) for pattern, parser in \
                         self.parsers if re.match(pattern, val)),
                        None) or self.get_column(val)
        if isinstance(val, Sequence):
            if len(val) == 1:
                return self.parse_identifier(val[0])
            else:
                return self.parse_single_expression(val)

        else:
            return None

    def parse_single_expression(self, expr):
        if isinstance(expr, str):
            return self.parse_identifier(expr)
        elif isinstance(expr, Sequence):
            if len(expr) == 1:
                return self.parse_single_expression(expr[0])
            else:
                if isinstance(expr[0], str) and expr[0].lower() in self.func_map:
                    arguments = map(self.parse_identifier, expr[1:])
                    return self.func_map[expr[0].lower()](*arguments)
                else:
                    if expr[1] in self.op_map:
                        operands = map(self.parse_identifier, expr[::2])
                        return self.op_map[expr[1]](*operands)
                    else:
                        raise NotImplementedError(f"Invalid operator {expr[1]} in OData expression")
        return None

    def create_filter(self, filter_string: str):
        parsed = self.filter_expression.parseString(filter_string)
        return self.parse_single_expression(parsed)

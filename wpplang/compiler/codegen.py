"""The Python code generator.

Walks the W++ AST and emits Python source.  It reads only the tree - there is
no keyword substitution anywhere in this module - so the mapping from W++ to
Python lives in exactly one place: the KEYWORDS table, consulted here when a
node names a W++ word.

While emitting, the generator records which W++ line each generated Python line
came from.  That map is what lets a Python exception be reported against the
W++ the author wrote.
"""

from ..keywords import KEYWORDS
from . import nodes as N

# The Python each W++ construct is written with.  Taken from the dictionary so
# the table stays the single source of truth.
PY = KEYWORDS

_CONSTANTS = {"nocap": "True", "cap": "False", "npc": "None"}


class SourceMap:
    """Which W++ line produced each generated Python line."""

    def __init__(self):
        self._to_wpp = {}

    def record(self, python_line, wpp_line):
        if wpp_line:
            self._to_wpp[python_line] = wpp_line

    def wpp_line_for(self, python_line):
        """The W++ line for a Python line, or the nearest one above it."""
        if python_line in self._to_wpp:
            return self._to_wpp[python_line]
        candidates = [line for line in self._to_wpp if line <= python_line]
        if not candidates:
            return None
        return self._to_wpp[max(candidates)]

    def as_dict(self):
        return dict(self._to_wpp)


def generate(program):
    """Generate Python source for a Program.  Returns (source, SourceMap)."""
    emitter = _Emitter()
    if program.body:
        emitter.statements(program.body)
    # An empty program generates nothing. `pass` is only needed to fill a block
    # that would otherwise be empty, and a whole file is not a block.
    return emitter.finish()


class _Emitter:
    def __init__(self):
        self.lines = []
        self.map = SourceMap()
        # How many physical lines have been written. An emitted statement can
        # occupy more than one - a triple-quoted string carries its own
        # newlines - so this cannot be inferred from len(self.lines).
        self.physical = 0

    # -- output

    def emit(self, text, indent, node=None):
        """Write one line of Python, on the W++ line it came from where it can.

        Statements are padded down to the line their W++ counterpart occupies.
        It costs a few blank lines and buys two things: `--emit` output that
        lines up with the source the author is reading, and a source map that
        is exact rather than approximate.  When a W++ line yields more than one
        Python line the alignment cannot hold, and the map carries the truth
        instead.
        """
        wanted = getattr(node, "line", None) if node is not None else None
        if wanted:
            while self.physical < wanted - 1:
                self.lines.append("")
                self.physical += 1

        self.lines.append("    " * indent + text)
        start = self.physical + 1
        self.physical += 1 + text.count(chr(10))
        if wanted:
            self.map.record(start, wanted)

    def finish(self):
        if not self.lines:
            return "", self.map
        return chr(10).join(self.lines) + chr(10), self.map

    # -- statements

    def statements(self, body, indent=0):
        if body is None:
            self.emit("pass", indent)
            return
        if not isinstance(body, list):
            body = [body]
        if not body:
            self.emit("pass", indent)
            return
        for statement in body:
            self.statement(statement, indent)

    def statement(self, node, indent):
        kind = type(node).__name__
        handler = getattr(self, "_" + kind, None)
        if handler is None:
            if kind == "_Sequence":
                for item in node.statements:
                    self.statement(item, indent)
                return
            raise NotImplementedError("no code generation for " + kind)
        handler(node, indent)

    def _FunctionDeclaration(self, node, indent):
        for decorator in node.decorators or []:
            self.emit("@" + self.expression(decorator), indent, node)
        header = "{}{} {}({})".format(
            "async " if node.is_async else "", PY["cook"], node.name,
            self.parameters(node.params))
        if node.returns is not None:
            header += " -> " + self.expression(node.returns)
        self.emit(header + ":", indent, node)
        self.statements(node.body, indent + 1)

    def _ClassDeclaration(self, node, indent):
        for decorator in node.decorators or []:
            self.emit("@" + self.expression(decorator), indent, node)
        pieces = [self.expression(base) for base in node.bases or []]
        pieces += [self.keyword_argument(item) for item in node.keywords or []]
        header = "class " + node.name
        if pieces:
            header += "(" + ", ".join(pieces) + ")"
        self.emit(header + ":", indent, node)
        self.statements(node.body, indent + 1)

    def _ReturnStatement(self, node, indent):
        if node.value is None:
            self.emit(PY["spill"], indent, node)
        else:
            self.emit("{} {}".format(PY["spill"], self.expression(node.value)),
                      indent, node)

    def _IfStatement(self, node, indent):
        for position, (condition, body) in enumerate(node.branches):
            word = PY["bet"] if position == 0 else PY["plotwist"]
            self.emit("{} {}:".format(word, self.expression(condition)),
                      indent, node)
            self.statements(body, indent + 1)
        if node.orelse is not None:
            self.emit(PY["nah"] + ":", indent, node)
            self.statements(node.orelse, indent + 1)

    def _ForStatement(self, node, indent):
        self.emit("{}{} {} in {}:".format(
            "async " if node.is_async else "", PY["spam"],
            self.target(node.target), self.expression(node.iterable)),
            indent, node)
        self.statements(node.body, indent + 1)
        if node.orelse is not None:
            self.emit(PY["nah"] + ":", indent, node)
            self.statements(node.orelse, indent + 1)

    def _WhileStatement(self, node, indent):
        self.emit("{} {}:".format(PY["grind"], self.expression(node.condition)),
                  indent, node)
        self.statements(node.body, indent + 1)
        if node.orelse is not None:
            self.emit(PY["nah"] + ":", indent, node)
            self.statements(node.orelse, indent + 1)

    def _BreakStatement(self, node, indent):
        self.emit(PY["dip"], indent, node)

    def _ContinueStatement(self, node, indent):
        self.emit(PY["skrrt"], indent, node)

    def _PassStatement(self, node, indent):
        self.emit("pass", indent, node)

    def _Assignment(self, node, indent):
        targets = " = ".join(self.target(target) for target in node.targets)
        self.emit("{} = {}".format(targets, self.expression(node.value)),
                  indent, node)

    def _AugmentedAssignment(self, node, indent):
        self.emit("{} {} {}".format(self.target(node.target), node.operator,
                                    self.expression(node.value)), indent, node)

    def _AnnotatedAssignment(self, node, indent):
        text = "{}: {}".format(self.target(node.target),
                               self.expression(node.annotation))
        if node.value is not None:
            text += " = " + self.expression(node.value)
        self.emit(text, indent, node)

    def _ExpressionStatement(self, node, indent):
        self.emit(self.expression(node.expression), indent, node)

    def _TryStatement(self, node, indent):
        self.emit("try:", indent, node)
        self.statements(node.body, indent + 1)
        for handler in node.handlers or []:
            header = "except"
            if handler.is_star:
                header += "*"
            if handler.type is not None:
                header += " " + self.expression(handler.type)
            if handler.name:
                header += " as " + handler.name
            self.emit(header + ":", indent, handler)
            self.statements(handler.body, indent + 1)
        if node.orelse is not None:
            self.emit(PY["nah"] + ":", indent, node)
            self.statements(node.orelse, indent + 1)
        if node.finalbody is not None:
            self.emit("finally:", indent, node)
            self.statements(node.finalbody, indent + 1)

    def _WithStatement(self, node, indent):
        pieces = []
        for item in node.items:
            text = self.expression(item.context)
            if item.target is not None:
                text += " as " + self.target(item.target)
            pieces.append(text)
        self.emit("{}with {}:".format("async " if node.is_async else "",
                                      ", ".join(pieces)), indent, node)
        self.statements(node.body, indent + 1)

    def _RaiseStatement(self, node, indent):
        text = "raise"
        if node.exception is not None:
            text += " " + self.expression(node.exception)
            if node.cause is not None:
                text += " from " + self.expression(node.cause)
        self.emit(text, indent, node)

    def _AssertStatement(self, node, indent):
        text = "assert " + self.expression(node.test)
        if node.message is not None:
            text += ", " + self.expression(node.message)
        self.emit(text, indent, node)

    def _ImportStatement(self, node, indent):
        pieces = [alias.name + (" as " + alias.asname if alias.asname else "")
                  for alias in node.names]
        self.emit("import " + ", ".join(pieces), indent, node)

    def _ImportFromStatement(self, node, indent):
        pieces = [alias.name + (" as " + alias.asname if alias.asname else "")
                  for alias in node.names]
        self.emit("from {}{} import {}".format(
            "." * (node.level or 0), node.module or "", ", ".join(pieces)),
            indent, node)

    def _GlobalStatement(self, node, indent):
        self.emit("global " + ", ".join(node.names), indent, node)

    def _NonlocalStatement(self, node, indent):
        self.emit("nonlocal " + ", ".join(node.names), indent, node)

    def _DeleteStatement(self, node, indent):
        self.emit("del " + ", ".join(self.target(t) for t in node.targets),
                  indent, node)

    def _MatchStatement(self, node, indent):
        self.emit("match {}:".format(self.expression(node.subject)), indent, node)
        for case in node.cases:
            header = "case " + case.pattern
            if case.guard is not None:
                header += " if " + self.expression(case.guard)
            self.emit(header + ":", indent + 1, case)
            self.statements(case.body, indent + 2)

    # -- parameters and arguments

    def parameters(self, params):
        pieces = []
        positional_only = [p for p in params if p.kind == "positional_only"]
        seen_keyword_only = False
        seen_vararg = False

        for index, param in enumerate(params):
            if param.kind == "vararg":
                pieces.append("*" + param.name)
                seen_vararg = True
                continue
            if param.kind == "kwarg":
                pieces.append("**" + param.name)
                continue
            if param.kind == "keyword_only" and not seen_vararg and not seen_keyword_only:
                pieces.append("*")
                seen_keyword_only = True

            text = param.name
            if param.annotation is not None:
                text += ": " + self.expression(param.annotation)
            if param.default is not None:
                text += ("=" if param.annotation is None else " = ") \
                    + self.expression(param.default)
            pieces.append(text)

            if positional_only and param is positional_only[-1]:
                pieces.append("/")
        return ", ".join(pieces)

    def keyword_argument(self, item):
        if item.name is None:
            return "**" + self.expression(item.value)
        return "{}={}".format(item.name, self.expression(item.value))

    def target(self, node):
        """A target is written the same way as an expression."""
        return self.expression(node)

    # -- expressions

    def expression(self, node):
        if node is None:
            return ""
        kind = type(node).__name__
        handler = getattr(self, "_e_" + kind, None)
        if handler is None:
            raise NotImplementedError("no code generation for " + kind)
        return handler(node)

    def _e_Literal(self, node):
        if node.kind == "constant":
            return _CONSTANTS[node.value]
        # Numbers and strings are emitted exactly as written, which is the only
        # correct thing to do with the contents of a string literal.
        return node.raw

    def _e_Identifier(self, node):
        # A W++ word standing in for a builtin: `squad` -> `list`.
        return KEYWORDS.get(node.name, node.name)

    def _e_FStringLiteral(self, node):
        """Rebuild the f-string, regenerating only its replacement fields."""
        fields = getattr(node, "parsed_fields", None)
        if not fields or node.start is None:
            return node.raw

        pieces = []
        cursor = node.start
        for field in fields:
            if field["start"] is None:
                continue
            pieces.append(node.raw[cursor - node.start:field["start"] - node.start])
            pieces.append(self.expression(field["expression"]))
            cursor = field["end"]
        pieces.append(node.raw[cursor - node.start:])
        return "".join(pieces)

    def _e_BinaryExpression(self, node):
        return "({} {} {})".format(self.expression(node.left), node.operator,
                                   self.expression(node.right))

    def _e_UnaryExpression(self, node):
        if node.operator == "not":
            return "(not {})".format(self.expression(node.operand))
        return "({}{})".format(node.operator, self.expression(node.operand))

    def _e_BooleanExpression(self, node):
        joiner = " {} ".format(node.operator)
        return "(" + joiner.join(self.expression(v) for v in node.values) + ")"

    def _e_ComparisonExpression(self, node):
        text = self.expression(node.left)
        for operator, comparator in zip(node.operators, node.comparators):
            text += " {} {}".format(operator, self.expression(comparator))
        return "(" + text + ")"

    def _e_ConditionalExpression(self, node):
        return "({} if {} else {})".format(
            self.expression(node.body), self.expression(node.test),
            self.expression(node.orelse))

    def _e_CallExpression(self, node):
        pieces = [self.expression(arg) for arg in node.args or []]
        pieces += [self.keyword_argument(item) for item in node.keywords or []]
        return "{}({})".format(self.expression(node.callee), ", ".join(pieces))

    def _e_AttributeExpression(self, node):
        # The attribute name is never a keyword, so it is emitted as written.
        return "{}.{}".format(self.expression(node.value), node.name)

    def _e_IndexExpression(self, node):
        return "{}[{}]".format(self.expression(node.value),
                               self.subscript(node.index))

    def subscript(self, node):
        if isinstance(node, N.TupleLiteral) and not node.parenthesised:
            return ", ".join(self.subscript(item) for item in node.elements)
        if isinstance(node, N.SliceExpression):
            return self._e_SliceExpression(node)
        return self.expression(node)

    def _e_SliceExpression(self, node):
        text = self.expression(node.lower) + ":" + self.expression(node.upper)
        if node.step is not None:
            text += ":" + self.expression(node.step)
        return text

    def _e_ListLiteral(self, node):
        return "[" + ", ".join(self.expression(e) for e in node.elements) + "]"

    def _e_TupleLiteral(self, node):
        if not node.elements:
            return "()"
        inside = ", ".join(self.expression(e) for e in node.elements)
        if len(node.elements) == 1:
            inside += ","
        return "(" + inside + ")"

    def _e_SetLiteral(self, node):
        return "{" + ", ".join(self.expression(e) for e in node.elements) + "}"

    def _e_DictLiteral(self, node):
        pieces = []
        for key, value in node.pairs:
            if key is None:
                pieces.append("**" + self.expression(value))
            else:
                pieces.append("{}: {}".format(self.expression(key),
                                              self.expression(value)))
        return "{" + ", ".join(pieces) + "}"

    def _e_Comprehension(self, node):
        if node.kind == "dict":
            head = "{}: {}".format(self.expression(node.element),
                                   self.expression(node.value))
        else:
            head = self.expression(node.element)

        clauses = ""
        for clause in node.clauses:
            clauses += " {}{} {} in {}".format(
                "async " if clause.is_async else "", PY["spam"],
                self.target(clause.target), self.expression(clause.iterable))
            for condition in clause.conditions:
                clauses += " {} {}".format(PY["bet"], self.expression(condition))

        body = head + clauses
        if node.kind == "list":
            return "[" + body + "]"
        if node.kind == "set":
            return "{" + body + "}"
        if node.kind == "dict":
            return "{" + body + "}"
        return "(" + body + ")"

    def _e_LambdaExpression(self, node):
        params = self.parameters(node.params)
        return "(lambda{}: {})".format(" " + params if params else "",
                                       self.expression(node.body))

    def _e_StarredExpression(self, node):
        return ("**" if node.double else "*") + self.expression(node.value)

    def _e_WalrusExpression(self, node):
        return "({} := {})".format(self.expression(node.target),
                                   self.expression(node.value))

    def _e_YieldExpression(self, node):
        if node.is_from:
            return "(yield from {})".format(self.expression(node.value))
        if node.value is None:
            return "(yield)"
        return "(yield {})".format(self.expression(node.value))

    def _e_AwaitExpression(self, node):
        return "(await {})".format(self.expression(node.value))

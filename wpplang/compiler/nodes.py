"""The W++ abstract syntax tree.

These nodes describe W++ constructs, not fragments of Python text.  A `cook`
declaration becomes a FunctionDeclaration that knows its name, its parameters
and its body; nothing anywhere in the tree holds a half-translated string.  The
Python backend is one consumer of this tree, and the tree would survive being
given a different backend.

Every node records the line and column it started at, which is what lets an
error talk about the W++ the author wrote.
"""


class Node:
    """Base class: a position, a field list, and a readable dump."""

    _fields = ()

    def __init__(self, line=None, column=None):
        self.line = line
        self.column = column

    def dump(self, indent=0):
        """Render the subtree as indented text.  Used by `wpp.py --ast`."""
        pad = "  " * indent
        head = "{}{}".format(pad, type(self).__name__)
        details = []
        children = []

        for name in self._fields:
            value = getattr(self, name, None)
            if isinstance(value, Node):
                children.append((name, value))
            elif isinstance(value, (list, tuple)):
                if value and all(isinstance(item, Node) for item in value):
                    children.append((name, list(value)))
                elif value and isinstance(value[0], tuple):
                    children.append((name, list(value)))
                elif value:
                    details.append("{}={!r}".format(name, list(value)))
            elif value is False:
                # A flag that is off says nothing; leaving `is_async=False` and
                # friends out keeps a dump readable.
                continue
            elif value is not None:
                details.append("{}={!r}".format(name, value))

        if self.line is not None:
            details.append("@{}:{}".format(self.line, self.column))
        if details:
            head += "  " + " ".join(details)

        lines = [head]
        for name, child in children:
            lines.append("{}  {}:".format(pad, name))
            for item in (child if isinstance(child, list) else [child]):
                if isinstance(item, Node):
                    lines.append(item.dump(indent + 2))
                elif isinstance(item, tuple):
                    lines.append("{}    (".format(pad))
                    for piece in item:
                        if isinstance(piece, Node):
                            lines.append(piece.dump(indent + 3))
                        elif isinstance(piece, list):
                            for sub in piece:
                                lines.append(sub.dump(indent + 3))
                        else:
                            lines.append("{}      {!r}".format(pad, piece))
                    lines.append("{}    )".format(pad))
        return "\n".join(lines)

    def __repr__(self):
        inside = ", ".join(
            "{}={!r}".format(name, getattr(self, name, None)) for name in self._fields)
        return "{}({})".format(type(self).__name__, inside)


def _node(name, fields, base=Node, doc=None):
    """Build a node class with the given fields.

    Written as a factory because there are a lot of these and spelling out
    thirty near-identical __init__ methods would bury the interesting parts.
    """

    def __init__(self, *values, **kwargs):
        line = kwargs.pop("line", None)
        column = kwargs.pop("column", None)
        base.__init__(self, line=line, column=column)
        if len(values) > len(fields):
            raise TypeError("{} takes {} fields".format(name, len(fields)))
        for index, field in enumerate(fields):
            if index < len(values):
                setattr(self, field, values[index])
            else:
                setattr(self, field, kwargs.pop(field, None))
        if kwargs:
            raise TypeError("unexpected fields for {}: {}".format(
                name, ", ".join(sorted(kwargs))))

    return type(name, (base,), {
        "__init__": __init__, "_fields": tuple(fields), "__doc__": doc,
    })


# --------------------------------------------------------------- the program

Program = _node("Program", ["body"], doc="A whole W++ file.")


# -------------------------------------------------------------- declarations

Parameter = _node(
    "Parameter", ["name", "default", "kind", "annotation"],
    doc="One parameter. `kind` is normal, vararg, kwarg, keyword_only or "
        "positional_only.")

FunctionDeclaration = _node(
    "FunctionDeclaration", ["name", "params", "body", "decorators", "is_async",
                            "returns", "keyword"],
    doc="A `cook` declaration. `keyword` records the W++ word that opened it.")

ClassDeclaration = _node(
    "ClassDeclaration", ["name", "bases", "keywords", "body", "decorators"],
    doc="A `class` declaration. W++ does not rename `class`.")


# ---------------------------------------------------------------- statements

ReturnStatement = _node("ReturnStatement", ["value", "keyword"],
                        doc="`spill`.")
IfStatement = _node("IfStatement", ["branches", "orelse"],
                    doc="`bet` plus any `plotwist` branches plus an optional "
                        "`nah`. Each branch is (condition, body).")
ForStatement = _node("ForStatement", ["target", "iterable", "body", "orelse",
                                      "is_async", "keyword"],
                     doc="`spam`. `orelse` is a `nah` attached to the loop.")
WhileStatement = _node("WhileStatement", ["condition", "body", "orelse", "keyword"],
                       doc="`grind`.")
BreakStatement = _node("BreakStatement", ["keyword"], doc="`dip`.")
ContinueStatement = _node("ContinueStatement", ["keyword"], doc="`skrrt`.")
PassStatement = _node("PassStatement", [], doc="`pass`.")

Assignment = _node("Assignment", ["targets", "value"],
                   doc="`x = 1`, and chained forms like `a = b = 1`.")
AugmentedAssignment = _node("AugmentedAssignment", ["target", "operator", "value"],
                            doc="`x += 1`.")
AnnotatedAssignment = _node("AnnotatedAssignment", ["target", "annotation", "value"],
                            doc="`x: int = 1`.")
ExpressionStatement = _node("ExpressionStatement", ["expression"],
                            doc="An expression evaluated for its effect, such "
                                "as a bare `yap(...)` call.")

TryStatement = _node("TryStatement", ["body", "handlers", "orelse", "finalbody"],
                     doc="`try`, with a `nah` understood as its else clause.")
ExceptClause = _node("ExceptClause", ["type", "name", "body", "is_star"])
WithStatement = _node("WithStatement", ["items", "body", "is_async"])
WithItem = _node("WithItem", ["context", "target"])
RaiseStatement = _node("RaiseStatement", ["exception", "cause"])
AssertStatement = _node("AssertStatement", ["test", "message"])
ImportStatement = _node("ImportStatement", ["names"], doc="`import a.b as c`.")
ImportFromStatement = _node("ImportFromStatement", ["module", "names", "level"])
ImportAlias = _node("ImportAlias", ["name", "asname"])
GlobalStatement = _node("GlobalStatement", ["names"])
NonlocalStatement = _node("NonlocalStatement", ["names"])
DeleteStatement = _node("DeleteStatement", ["targets"])
MatchStatement = _node("MatchStatement", ["subject", "cases"])
MatchCase = _node("MatchCase", ["pattern", "guard", "body"],
                  doc="A `case`. The pattern is kept as its token text, since "
                      "W++ adds nothing to Python's pattern syntax.")


# --------------------------------------------------------------- expressions

Literal = _node("Literal", ["value", "raw", "kind"],
                doc="A number, string, or one of `nocap`/`cap`/`npc`. `raw` is "
                    "the source text, kept so a string is emitted exactly as "
                    "written.")
Identifier = _node("Identifier", ["name"])
FStringLiteral = _node("FStringLiteral", ["raw", "fields", "start"],
                       doc="An f-string. Its `{...}` fields are parsed "
                           "expressions; the literal text between them is "
                           "string content and is never touched.")

BinaryExpression = _node("BinaryExpression", ["left", "operator", "right"])
UnaryExpression = _node("UnaryExpression", ["operator", "operand"])
BooleanExpression = _node("BooleanExpression", ["operator", "values"],
                          doc="`and` / `or`, which W++ does not rename.")
ComparisonExpression = _node("ComparisonExpression", ["left", "operators", "comparators"],
                             doc="Supports chains such as `1 < x < 10`.")
ConditionalExpression = _node("ConditionalExpression", ["body", "test", "orelse"],
                              doc="`value bet condition nah other`.")

CallExpression = _node("CallExpression", ["callee", "args", "keywords"])
KeywordArgument = _node("KeywordArgument", ["name", "value"],
                        doc="`f(x=1)`, or `f(**rest)` when name is None.")
AttributeExpression = _node("AttributeExpression", ["value", "name"])
IndexExpression = _node("IndexExpression", ["value", "index"])
SliceExpression = _node("SliceExpression", ["lower", "upper", "step"])

ListLiteral = _node("ListLiteral", ["elements"], doc="`[1, 2]`, or `squad(...)`.")
TupleLiteral = _node("TupleLiteral", ["elements", "parenthesised"])
SetLiteral = _node("SetLiteral", ["elements"])
DictLiteral = _node("DictLiteral", ["pairs"],
                    doc="Pairs of (key, value); a key of None means `**other`.")

Comprehension = _node("Comprehension", ["kind", "element", "value", "clauses"],
                      doc="kind is list, set, dict or generator. `value` is "
                          "only used by a dict comprehension.")
ComprehensionClause = _node("ComprehensionClause", ["target", "iterable",
                                                    "conditions", "is_async"],
                            doc="One `spam ... in ...` with any `bet` filters.")

LambdaExpression = _node("LambdaExpression", ["params", "body"])
StarredExpression = _node("StarredExpression", ["value", "double"])
WalrusExpression = _node("WalrusExpression", ["target", "value"])
YieldExpression = _node("YieldExpression", ["value", "is_from"])
AwaitExpression = _node("AwaitExpression", ["value"])

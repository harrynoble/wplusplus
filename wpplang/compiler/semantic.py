"""Semantic validation of a W++ program.

The parser answers "is this W++?".  This stage answers the questions that need
a view of the whole tree: is `dip` inside a loop, is `spill` inside a `cook`,
does anything try to use a keyword as a name.  Catching these here means the
error names the W++ word and the W++ line, instead of arriving later as a
complaint about generated Python.

Deliberately small.  W++ is dynamically typed, so there is no type checking to
do and inventing some would change the language.
"""

from ..keywords import KEYWORDS
from .errors import WppSemanticError
from . import nodes as N


def validate(program, source=None):
    """Check a Program.  Raises WppSemanticError on the first problem."""
    _Checker(source).program(program)
    return program


class _Checker:
    def __init__(self, source=None):
        self.lines = source.splitlines() if source else []

    def fail(self, message, node):
        raise WppSemanticError(
            message, line=node.line, column=node.column,
            source_line=self._text(node.line))

    def _text(self, line):
        if line and 1 <= line <= len(self.lines):
            return self.lines[line - 1]
        return None

    # -- walking

    def program(self, program):
        self.block(program.body, in_loop=False, in_function=False)

    def block(self, body, in_loop, in_function):
        if body is None:
            return
        if not isinstance(body, list):
            body = [body]
        for statement in body:
            self.statement(statement, in_loop, in_function)

    def statement(self, node, in_loop, in_function):
        if isinstance(node, N.BreakStatement):
            if not in_loop:
                self.fail("`dip` only means something inside a `spam` or "
                          "`grind` loop", node)
            return
        if isinstance(node, N.ContinueStatement):
            if not in_loop:
                self.fail("`skrrt` only means something inside a `spam` or "
                          "`grind` loop", node)
            return
        if isinstance(node, N.ReturnStatement):
            if not in_function:
                self.fail("`spill` only means something inside a `cook` "
                          "function", node)
            return

        if isinstance(node, N.FunctionDeclaration):
            self.check_name(node.name, node)
            seen = set()
            for param in node.params:
                self.check_name(param.name, param)
                if param.name in seen:
                    self.fail("`{}` is listed twice in this parameter "
                              "list".format(param.name), param)
                seen.add(param.name)
            # A loop does not reach into a nested function.
            self.block(node.body, in_loop=False, in_function=True)
            return

        if isinstance(node, N.ClassDeclaration):
            self.check_name(node.name, node)
            self.block(node.body, in_loop=False, in_function=in_function)
            return

        if isinstance(node, N.IfStatement):
            for _condition, body in node.branches:
                self.block(body, in_loop, in_function)
            self.block(node.orelse, in_loop, in_function)
            return

        if isinstance(node, N.ForStatement):
            self.block(node.body, in_loop=True, in_function=in_function)
            self.block(node.orelse, in_loop, in_function)
            return

        if isinstance(node, N.WhileStatement):
            self.block(node.body, in_loop=True, in_function=in_function)
            self.block(node.orelse, in_loop, in_function)
            return

        if isinstance(node, N.TryStatement):
            self.block(node.body, in_loop, in_function)
            for handler in node.handlers or []:
                self.block(handler.body, in_loop, in_function)
            self.block(node.orelse, in_loop, in_function)
            self.block(node.finalbody, in_loop, in_function)
            return

        if isinstance(node, N.WithStatement):
            self.block(node.body, in_loop, in_function)
            return

        if isinstance(node, N.MatchStatement):
            for case in node.cases:
                self.block(case.body, in_loop, in_function)
            return

        if isinstance(node, N.Assignment):
            for target in node.targets:
                self.check_target(target)
            return

        if type(node).__name__ == "_Sequence":
            for item in node.statements:
                self.statement(item, in_loop, in_function)
            return

    # -- names

    def check_name(self, name, node):
        """A definition may not be named after a W++ keyword."""
        if name in KEYWORDS:
            self.fail(
                "'{}' is a W++ keyword (it becomes Python's '{}'), so it "
                "cannot be used as a name".format(name, KEYWORDS[name]), node)

    def check_target(self, target):
        """Assigning to a keyword is the same mistake, spelled differently."""
        name = None
        if isinstance(target, N.Identifier) and target.name in KEYWORDS:
            name = target.name
        elif isinstance(target, N.Literal) and target.kind == "constant":
            # `nocap`, `cap` and `npc` parse as values, so they arrive here as
            # literals rather than names - but `cap = 1` is the same mistake,
            # and without this it would reach Python as `False = 1`.
            name = target.value

        if name is not None:
            self.fail(
                "'{}' is a W++ keyword (it becomes Python's '{}'), so it "
                "cannot be assigned to".format(name, KEYWORDS[name]), target)

        if isinstance(target, (N.TupleLiteral, N.ListLiteral)):
            for element in target.elements:
                self.check_target(element)
        elif isinstance(target, N.StarredExpression):
            self.check_target(target.value)

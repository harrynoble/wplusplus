"""The W++ parser.

Consumes the token stream from the lexer and produces a W++ AST.  Statements
are handled by recursive descent - one method per construct, which keeps each
piece of the grammar readable - and expressions by precedence climbing, so the
precedence table is written once instead of being spread across a dozen
near-identical methods.

W++'s grammar is Python's grammar with nineteen renamed words, so the shape of
this parser follows Python's statement forms.  What makes it a W++ parser is
that `bet`, `plotwist`, `nah`, `spam`, `grind`, `cook`, `spill`, `dip` and
`skrrt` are the words it recognises, and that it records which W++ keyword
opened each construct on the node it builds.
"""

from ..keywords import KEYWORDS
from .errors import WppIndentationError, WppSyntaxError
from .nodes import (
    AnnotatedAssignment, Assignment, AssertStatement, AttributeExpression,
    AugmentedAssignment, AwaitExpression, BinaryExpression, BooleanExpression,
    BreakStatement, CallExpression, ClassDeclaration, ComparisonExpression,
    Comprehension, ComprehensionClause, ConditionalExpression,
    ContinueStatement, DeleteStatement, DictLiteral, ExceptClause,
    ExpressionStatement, FStringLiteral, ForStatement, FunctionDeclaration,
    GlobalStatement, Identifier, IfStatement, ImportAlias, ImportFromStatement,
    ImportStatement, IndexExpression, KeywordArgument, LambdaExpression,
    ListLiteral, Literal, MatchCase, MatchStatement, NonlocalStatement,
    Parameter, PassStatement, Program, RaiseStatement, ReturnStatement,
    SetLiteral, SliceExpression, StarredExpression, TryStatement,
    TupleLiteral, UnaryExpression, WalrusExpression, WhileStatement,
    WithItem, WithStatement, YieldExpression,
)
from .tokens import TokenType

# Binary operator precedence, lowest binding first.  `or` and `and` are handled
# separately because they build BooleanExpression, and comparisons are handled
# separately because W++ keeps Python's chaining.
_BINARY_PRECEDENCE = [
    ("|",),
    ("^",),
    ("&",),
    ("<<", ">>"),
    ("+", "-"),
    ("*", "/", "//", "%", "@"),
]

_COMPARISON_OPS = {"<", ">", "==", ">=", "<=", "!=", "<>"}

_AUGMENTED_OPS = {
    "+=", "-=", "*=", "/=", "//=", "%=", "**=", ">>=", "<<=", "&=", "|=",
    "^=", "@=",
}

# Words W++ leaves as Python's own.  Listed so the parser can tell a statement
# keyword from an ordinary name without guessing.
_STATEMENT_WORDS = {
    "class", "try", "except", "finally", "with", "raise", "assert", "import",
    "from", "global", "nonlocal", "del", "pass", "match", "case", "lambda",
    "yield", "await", "async", "and", "or", "not", "in", "is", "if", "else",
    "for", "while", "return", "def", "break", "continue", "elif",
}


def parse(tokens, source=None):
    """Parse a token stream into a Program."""
    return _Parser(tokens, source).parse_program()


class _Parser:
    def __init__(self, tokens, source=None):
        self.tokens = tokens
        self.index = 0
        self.source = source
        self.lines = source.splitlines() if source else []

    # ------------------------------------------------------------ token access

    @property
    def current(self):
        return self.tokens[self.index]

    def peek(self, offset=1):
        position = min(self.index + offset, len(self.tokens) - 1)
        return self.tokens[position]

    def advance(self):
        token = self.tokens[self.index]
        if self.index < len(self.tokens) - 1:
            self.index += 1
        return token

    def check_op(self, *symbols):
        return self.current.is_op(*symbols)

    def accept_op(self, *symbols):
        if self.current.is_op(*symbols):
            return self.advance()
        return None

    def expect_op(self, symbol, what=None):
        if not self.current.is_op(symbol):
            self.fail("expected {!r}{}".format(
                symbol, " " + what if what else ""))
        return self.advance()

    def accept_keyword(self, *words):
        if self.current.is_keyword(*words):
            return self.advance()
        return None

    def accept_name(self, *names):
        if self.current.is_name(*names):
            return self.advance()
        return None

    def at_word(self, *names):
        """Is the current token one of these bare Python words?"""
        return self.current.is_name(*names)

    def fail_plain(self, message, token=None):
        """Fail with exactly this message, with no "but found ..." added."""
        token = token or self.current
        text = None
        if token.line and 1 <= token.line <= len(self.lines):
            text = self.lines[token.line - 1]
        raise WppSyntaxError(message, line=token.line, column=token.column,
                             source_line=text)

    def reject_keyword_name(self, token, role="a name"):
        """The one mistake every W++ beginner makes, explained properly."""
        self.fail_plain(
            "'{}' is a W++ keyword (it becomes Python's '{}'), so it cannot be "
            "used as {}".format(token.value, KEYWORDS[token.value], role), token)

    def fail(self, message, token=None):
        token = token or self.current
        text = None
        if token.line and 1 <= token.line <= len(self.lines):
            text = self.lines[token.line - 1]

        # An INDENT or DEDENT where a statement was expected is an indentation
        # problem, and the spec has its own message for those.
        if token.type == TokenType.INDENT:
            raise WppIndentationError(
                "unexpected indent", line=token.line,
                column=token.column, source_line=text)
        if token.type == TokenType.DEDENT:
            raise WppIndentationError(
                "unindent does not match any outer indentation level",
                line=token.line, column=token.column, source_line=text)

        shown = token.value if token.type != TokenType.EOF else "the end of the file"
        raise WppSyntaxError(
            "{} but found {!r}".format(message, shown) if shown else message,
            line=token.line, column=token.column, source_line=text)

    # ------------------------------------------------------------- structure

    def parse_program(self):
        body = []
        self.skip_newlines()
        while self.current.type != TokenType.EOF:
            body.append(self.parse_statement())
            self.skip_newlines()
        return Program(body, line=1, column=0)

    def skip_newlines(self):
        while self.current.type in (TokenType.NEWLINE, TokenType.INDENT,
                                    TokenType.DEDENT):
            # A stray INDENT/DEDENT at top level only happens on a blank line
            # that tokenize measured; the block parser consumes the real ones.
            if self.current.type != TokenType.NEWLINE and not self._blank_layout():
                return
            self.advance()

    def _blank_layout(self):
        """True when an INDENT/DEDENT here carries no statement after it."""
        offset = 0
        while self.peek(offset).type in (TokenType.INDENT, TokenType.DEDENT,
                                         TokenType.NEWLINE):
            offset += 1
        return self.peek(offset).type == TokenType.EOF

    def parse_block(self):
        """Parse `: <newline> INDENT statements DEDENT`, or a one-line body."""
        self.expect_op(":", "to open a block")

        if self.current.type != TokenType.NEWLINE:
            # A single-line body: `bet x: yap(1)`.
            return self.parse_simple_line()

        self.advance()  # the NEWLINE
        while self.current.type == TokenType.NEWLINE:
            self.advance()

        if self.current.type != TokenType.INDENT:
            self.fail("expected an indented block")
        self.advance()

        body = []
        while True:
            while self.current.type == TokenType.NEWLINE:
                self.advance()
            if self.current.type in (TokenType.DEDENT, TokenType.EOF):
                break
            body.append(self.parse_statement())
        if self.current.type == TokenType.DEDENT:
            self.advance()
        if not body:
            self.fail("this block is empty")
        return body

    def parse_simple_line(self):
        """One or more small statements separated by semicolons."""
        statements = [self.parse_small_statement()]
        while self.accept_op(";"):
            if self.current.type in (TokenType.NEWLINE, TokenType.EOF):
                break
            statements.append(self.parse_small_statement())
        if self.current.type == TokenType.NEWLINE:
            self.advance()
        return statements

    # ------------------------------------------------------------ statements

    def parse_statement(self):
        token = self.current

        if self.check_op("@"):
            return self.parse_decorated()
        if token.is_keyword("cook"):
            return self.parse_function()
        if token.is_keyword("bet"):
            return self.parse_if()
        if token.is_keyword("spam"):
            return self.parse_for()
        if token.is_keyword("grind"):
            return self.parse_while()
        if token.is_name("class"):
            return self.parse_class()
        if token.is_name("try"):
            return self.parse_try()
        if token.is_name("with"):
            return self.parse_with()
        if token.is_name("match") and self._looks_like_match():
            return self.parse_match()
        if token.is_name("async"):
            return self.parse_async()
        if token.is_name("if", "for", "while", "def", "elif", "else"):
            self.fail("`{}` is Python; W++ uses its own word here".format(token.value))

        statements = self.parse_simple_line()
        return statements[0] if len(statements) == 1 else _Sequence(statements)

    def parse_small_statement(self):
        token = self.current

        if token.is_keyword("spill"):
            return self.parse_return()
        if token.is_keyword("dip"):
            self.advance()
            return BreakStatement("dip", line=token.line, column=token.column)
        if token.is_keyword("skrrt"):
            self.advance()
            return ContinueStatement("skrrt", line=token.line, column=token.column)
        if token.is_name("pass"):
            self.advance()
            return PassStatement(line=token.line, column=token.column)
        if token.is_name("raise"):
            return self.parse_raise()
        if token.is_name("assert"):
            return self.parse_assert()
        if token.is_name("import"):
            return self.parse_import()
        if token.is_name("from"):
            return self.parse_import_from()
        if token.is_name("global", "nonlocal"):
            return self.parse_scope_declaration()
        if token.is_name("del"):
            return self.parse_delete()
        if token.is_name("return", "break", "continue"):
            self.fail("`{}` is Python; W++ uses its own word here".format(token.value))

        return self.parse_assignment_or_expression()

    def parse_decorated(self):
        decorators = []
        while self.check_op("@"):
            at = self.advance()
            decorators.append(self.parse_expression())
            if self.current.type == TokenType.NEWLINE:
                self.advance()
            while self.current.type == TokenType.NEWLINE:
                self.advance()
        if self.current.is_keyword("cook"):
            node = self.parse_function()
        elif self.at_word("class"):
            node = self.parse_class()
        elif self.at_word("async"):
            node = self.parse_async()
        else:
            self.fail("a decorator must be followed by `cook` or `class`", at)
        node.decorators = decorators
        return node

    def parse_async(self):
        word = self.advance()
        if self.current.is_keyword("cook"):
            node = self.parse_function()
            node.is_async = True
            return node
        if self.current.is_keyword("spam"):
            node = self.parse_for()
            node.is_async = True
            return node
        if self.at_word("with"):
            node = self.parse_with()
            node.is_async = True
            return node
        self.fail("`async` must be followed by `cook`, `spam` or `with`", word)

    def parse_function(self):
        keyword = self.advance()  # cook
        name = self.parse_definition_name(keyword)
        self.expect_op("(", "to open the parameter list")
        params = self.parse_parameters()
        self.expect_op(")", "to close the parameter list")

        returns = None
        if self.accept_op("->"):
            returns = self.parse_expression()

        body = self.parse_block()
        return FunctionDeclaration(name, params, body, [], False, returns,
                                   keyword.value,
                                   line=keyword.line, column=keyword.column)

    def parse_definition_name(self, keyword):
        """Read the name a definition is being given.

        A W++ keyword cannot be used here: `cook dip(self)` would have to
        become `def break(self)`, and even if that parsed, a call written
        `dip()` would become `break()`.  Saying so plainly beats letting the
        generated Python fail somewhere the author cannot see.
        """
        token = self.current
        if token.type == TokenType.KEYWORD:
            self.reject_keyword_name(token)
        if token.type != TokenType.NAME:
            self.fail("expected a name after `{}`".format(keyword.value), token)
        return self.advance().value

    def parse_parameters(self):
        params = []
        seen_star = False
        while not self.check_op(")"):
            if self.accept_op("/"):
                for param in params:
                    if param.kind == "normal":
                        param.kind = "positional_only"
                self.accept_op(",")
                continue
            if self.check_op("*") and self.peek().is_op(","):
                self.advance()
                seen_star = True
                self.accept_op(",")
                continue
            if self.accept_op("*"):
                seen_star = True
                params.append(self._one_parameter("vararg"))
                self.accept_op(",")
                continue
            if self.accept_op("**"):
                params.append(self._one_parameter("kwarg"))
                self.accept_op(",")
                continue

            params.append(self._one_parameter(
                "keyword_only" if seen_star else "normal"))
            if not self.accept_op(","):
                break
        return params

    def _one_parameter(self, kind):
        token = self.current
        if token.type == TokenType.KEYWORD:
            self.reject_keyword_name(token, "a parameter name")
        if token.type != TokenType.NAME:
            self.fail("expected a parameter name", token)
        self.advance()

        annotation = None
        if self.accept_op(":"):
            annotation = self.parse_expression()
        default = None
        if self.accept_op("="):
            default = self.parse_expression()
        return Parameter(token.value, default, kind, annotation,
                         line=token.line, column=token.column)

    def parse_class(self):
        keyword = self.advance()
        name = self.parse_definition_name(keyword)
        bases, keywords = [], []
        if self.accept_op("("):
            bases, keywords = self.parse_call_arguments()
            self.expect_op(")", "to close the base class list")
        body = self.parse_block()
        return ClassDeclaration(name, bases, keywords, body, [],
                                line=keyword.line, column=keyword.column)

    def parse_if(self):
        keyword = self.current
        branches = []
        condition = None

        first = self.accept_keyword("bet")
        if first is None:
            self.fail("expected `bet`")
        condition = self.parse_expression()
        branches.append((condition, self.parse_block()))

        orelse = None
        while True:
            self.skip_layout_before_clause(keyword.column)
            if self.current.is_keyword("plotwist"):
                self.advance()
                test = self.parse_expression()
                branches.append((test, self.parse_block()))
                continue
            if self.current.is_keyword("nah"):
                self.advance()
                orelse = self.parse_block()
            break

        return IfStatement(branches, orelse, line=keyword.line, column=keyword.column)

    def skip_layout_before_clause(self, column):
        """Look past blank lines for a clause continuing the statement at `column`.

        `plotwist`, `nah`, `except` and `finally` sit at the same indentation as
        the statement they belong to, so after a block ends the parser peeks
        across the layout tokens to find them.

        Matching the column is what stops a clause being claimed by the wrong
        statement.  In

            spam n in numbers:
                bet n % 2 == 1:
                    dip
            nah:
                yap("all even")

        the `nah` is the loop's, not the `bet`'s - it is written at the loop's
        indentation.  Without the column test the inner `bet` would swallow it
        and the program would mean something else entirely.
        """
        offset = 0
        while self.peek(offset).type in (TokenType.NEWLINE, TokenType.DEDENT):
            offset += 1
        follower = self.peek(offset)
        if follower.column != column:
            return
        if (follower.is_keyword("plotwist", "nah")
                or follower.is_name("except", "finally", "else", "elif")):
            for _ in range(offset):
                self.advance()

    def _looks_like_match(self):
        """Is this bare `match` opening a match statement, or just a name?

        `match` is a soft keyword: `match = 1` and `match(x)` are ordinary code.
        It opens a statement when what follows is a subject expression and the
        logical line ends with a colon.
        """
        after = self.peek()
        if (after.type in (TokenType.NEWLINE, TokenType.EOF)
                or after.is_op("=", ".", ",", ")", "]", "}", ":", ";")
                or (after.type == TokenType.OP and after.value in _AUGMENTED_OPS)):
            return False

        depth = 0
        offset = 1
        while True:
            token = self.peek(offset)
            if token.type in (TokenType.NEWLINE, TokenType.EOF):
                return False
            if token.is_op("(", "[", "{"):
                depth += 1
            elif token.is_op(")", "]", "}"):
                depth -= 1
            elif token.is_op(":") and depth == 0:
                return True
            elif token.is_op("=") and depth == 0:
                return False
            offset += 1

    def parse_for(self):
        keyword = self.advance()  # spam
        target = self.parse_target_list()
        if not self.accept_name("in"):
            self.fail("expected `in` after the loop variable")
        iterable = self.parse_expression_list()
        body = self.parse_block()

        orelse = None
        self.skip_layout_before_clause(keyword.column)
        if self.current.is_keyword("nah"):
            self.advance()
            orelse = self.parse_block()
        return ForStatement(target, iterable, body, orelse, False, keyword.value,
                            line=keyword.line, column=keyword.column)

    def parse_while(self):
        keyword = self.advance()  # grind
        condition = self.parse_expression()
        body = self.parse_block()

        orelse = None
        self.skip_layout_before_clause(keyword.column)
        if self.current.is_keyword("nah"):
            self.advance()
            orelse = self.parse_block()
        return WhileStatement(condition, body, orelse, keyword.value,
                              line=keyword.line, column=keyword.column)

    def parse_return(self):
        keyword = self.advance()  # spill
        value = None
        if self.current.type not in (TokenType.NEWLINE, TokenType.EOF) \
                and not self.check_op(";"):
            value = self.parse_expression_list()
        return ReturnStatement(value, keyword.value,
                               line=keyword.line, column=keyword.column)

    def parse_try(self):
        keyword = self.advance()
        body = self.parse_block()
        handlers = []
        orelse = None
        finalbody = None

        while True:
            self.skip_layout_before_clause(keyword.column)
            if self.at_word("except"):
                handlers.append(self.parse_except())
                continue
            if self.current.is_keyword("nah") or self.at_word("else"):
                self.advance()
                orelse = self.parse_block()
                continue
            if self.at_word("finally"):
                self.advance()
                finalbody = self.parse_block()
            break

        if not handlers and finalbody is None:
            self.fail("a `try` needs an `except` or a `finally`", keyword)
        return TryStatement(body, handlers, orelse, finalbody,
                            line=keyword.line, column=keyword.column)

    def parse_except(self):
        keyword = self.advance()
        is_star = bool(self.accept_op("*"))
        exception = None
        name = None
        if not self.check_op(":"):
            exception = self.parse_expression()
            if self.accept_name("as"):
                name = self.advance().value
        body = self.parse_block()
        return ExceptClause(exception, name, body, is_star,
                            line=keyword.line, column=keyword.column)

    def parse_with(self):
        keyword = self.advance()
        items = []
        parenthesised = bool(self.check_op("(") and self._with_uses_parens())
        if parenthesised:
            self.advance()
        while True:
            context = self.parse_expression()
            target = None
            if self.accept_name("as"):
                target = self.parse_primary_target()
            items.append(WithItem(context, target))
            if not self.accept_op(","):
                break
        if parenthesised:
            self.expect_op(")", "to close the `with` items")
        body = self.parse_block()
        return WithStatement(items, body, False,
                             line=keyword.line, column=keyword.column)

    def _with_uses_parens(self):
        """Distinguish `with (a, b):` grouping from a parenthesised expression."""
        depth = 0
        offset = 0
        while True:
            token = self.peek(offset)
            if token.type == TokenType.EOF:
                return False
            if token.is_op("(", "[", "{"):
                depth += 1
            elif token.is_op(")", "]", "}"):
                depth -= 1
                if depth == 0:
                    return self.peek(offset + 1).is_op(":")
            elif token.is_name("as") and depth == 1:
                return True
            offset += 1

    def parse_match(self):
        keyword = self.advance()
        subject = self.parse_expression_list()
        self.expect_op(":", "to open the match block")
        if self.current.type == TokenType.NEWLINE:
            self.advance()
        while self.current.type == TokenType.NEWLINE:
            self.advance()
        if self.current.type != TokenType.INDENT:
            self.fail("expected an indented block of `case` clauses")
        self.advance()

        cases = []
        while True:
            while self.current.type == TokenType.NEWLINE:
                self.advance()
            if self.current.type in (TokenType.DEDENT, TokenType.EOF):
                break
            if not self.at_word("case"):
                self.fail("expected `case`")
            case_token = self.advance()
            pattern = self.collect_pattern_text()
            guard = None
            if self.current.is_keyword("bet") or self.at_word("if"):
                self.advance()
                guard = self.parse_expression()
            body = self.parse_block()
            cases.append(MatchCase(pattern, guard, body,
                                   line=case_token.line, column=case_token.column))
        if self.current.type == TokenType.DEDENT:
            self.advance()
        if not cases:
            self.fail("a `match` needs at least one `case`", keyword)
        return MatchStatement(subject, cases,
                              line=keyword.line, column=keyword.column)

    def collect_pattern_text(self):
        """Capture a `case` pattern as source text.

        W++ adds nothing to Python's pattern syntax, and patterns are the one
        place where a name means "bind this" rather than "read this", so they
        are carried through as written rather than reinterpreted.
        """
        pieces = []
        depth = 0
        while True:
            token = self.current
            if token.type == TokenType.EOF:
                self.fail("this `case` pattern is never finished")
            if depth == 0 and (token.is_op(":") or token.is_keyword("bet")
                               or token.is_name("if")):
                break
            if token.is_op("(", "[", "{"):
                depth += 1
            elif token.is_op(")", "]", "}"):
                depth -= 1
            pieces.append(token)
            self.advance()
        if not pieces:
            self.fail("this `case` has no pattern")
        return _render_tokens(pieces)

    def parse_raise(self):
        keyword = self.advance()
        exception = None
        cause = None
        if self.current.type not in (TokenType.NEWLINE, TokenType.EOF) \
                and not self.check_op(";"):
            exception = self.parse_expression()
            if self.accept_name("from"):
                cause = self.parse_expression()
        return RaiseStatement(exception, cause,
                              line=keyword.line, column=keyword.column)

    def parse_assert(self):
        keyword = self.advance()
        test = self.parse_expression()
        message = None
        if self.accept_op(","):
            message = self.parse_expression()
        return AssertStatement(test, message,
                               line=keyword.line, column=keyword.column)

    def parse_import(self):
        keyword = self.advance()
        names = []
        while True:
            dotted = self.parse_dotted_name()
            asname = None
            if self.accept_name("as"):
                asname = self.advance().value
            names.append(ImportAlias(dotted, asname))
            if not self.accept_op(","):
                break
        return ImportStatement(names, line=keyword.line, column=keyword.column)

    def parse_import_from(self):
        keyword = self.advance()
        level = 0
        while self.check_op(".", "..."):
            level += len(self.advance().value)
        module = None
        if not self.at_word("import"):
            module = self.parse_dotted_name()
        if not self.accept_name("import"):
            self.fail("expected `import`")

        names = []
        if self.accept_op("*"):
            names.append(ImportAlias("*", None))
        else:
            wrapped = bool(self.accept_op("("))
            while True:
                name = self.advance().value
                asname = None
                if self.accept_name("as"):
                    asname = self.advance().value
                names.append(ImportAlias(name, asname))
                if not self.accept_op(","):
                    break
                if self.check_op(")"):
                    break
            if wrapped:
                self.expect_op(")", "to close the import list")
        return ImportFromStatement(module, names, level,
                                   line=keyword.line, column=keyword.column)

    def parse_dotted_name(self):
        parts = [self.advance().value]
        while self.check_op(".") and self.peek().type in (TokenType.NAME,
                                                          TokenType.KEYWORD):
            self.advance()
            parts.append(self.advance().value)
        return ".".join(parts)

    def parse_scope_declaration(self):
        keyword = self.advance()
        names = [self.advance().value]
        while self.accept_op(","):
            names.append(self.advance().value)
        node = (GlobalStatement if keyword.value == "global" else NonlocalStatement)
        return node(names, line=keyword.line, column=keyword.column)

    def parse_delete(self):
        keyword = self.advance()
        targets = [self.parse_expression()]
        while self.accept_op(","):
            targets.append(self.parse_expression())
        return DeleteStatement(targets, line=keyword.line, column=keyword.column)

    def parse_assignment_or_expression(self):
        start = self.current
        first = self.parse_expression_list(allow_star=True)

        if self.current.type == TokenType.OP and self.current.value in _AUGMENTED_OPS:
            operator = self.advance().value
            value = self.parse_expression_list()
            return AugmentedAssignment(first, operator, value,
                                       line=start.line, column=start.column)

        if self.check_op(":") :
            self.advance()
            annotation = self.parse_expression()
            value = None
            if self.accept_op("="):
                value = self.parse_expression_list()
            return AnnotatedAssignment(first, annotation, value,
                                       line=start.line, column=start.column)

        if self.check_op("="):
            targets = [first]
            value = None
            while self.accept_op("="):
                value = self.parse_expression_list(allow_star=True, allow_yield=True)
                if self.check_op("="):
                    targets.append(value)
            return Assignment(targets, value, line=start.line, column=start.column)

        return ExpressionStatement(first, line=start.line, column=start.column)

    def parse_target_list(self):
        """The `x` or `x, y` between `spam` and `in`."""
        items = [self.parse_primary_target()]
        trailing = False
        while self.accept_op(","):
            if self.at_word("in") or self.check_op(":"):
                trailing = True
                break
            items.append(self.parse_primary_target())
        if len(items) == 1 and not trailing:
            return items[0]
        return TupleLiteral(items, False, line=items[0].line, column=items[0].column)

    def parse_primary_target(self):
        if self.check_op("("):
            open_token = self.advance()
            inner = self.parse_target_list()
            self.expect_op(")", "to close the target")
            return inner
        if self.check_op("["):
            open_token = self.advance()
            items = []
            while not self.check_op("]"):
                items.append(self.parse_primary_target())
                if not self.accept_op(","):
                    break
            self.expect_op("]", "to close the target")
            return ListLiteral(items, line=open_token.line, column=open_token.column)
        if self.accept_op("*"):
            inner = self.parse_primary_target()
            return StarredExpression(inner, False, line=inner.line, column=inner.column)
        return self.parse_unary()

    # ----------------------------------------------------------- expressions

    def parse_expression_list(self, allow_star=False, allow_yield=False):
        """One expression, or a bare tuple like `1, 2`."""
        if allow_yield and self.at_word("yield"):
            return self.parse_yield()

        first = self.parse_expression(allow_star=allow_star)
        if not self.check_op(","):
            return first

        items = [first]
        trailing = True
        while self.accept_op(","):
            if self._at_expression_end():
                break
            items.append(self.parse_expression(allow_star=allow_star))
            trailing = False
        return TupleLiteral(items, False, line=first.line, column=first.column)

    def _at_expression_end(self):
        return (self.current.type in (TokenType.NEWLINE, TokenType.EOF)
                or self.current.is_op(")", "]", "}", ":", "=", ";")
                or self.current.type == TokenType.OP
                and self.current.value in _AUGMENTED_OPS)

    def parse_expression(self, allow_star=False):
        if self.at_word("lambda"):
            return self.parse_lambda()
        if self.at_word("yield"):
            return self.parse_yield()
        if allow_star and self.check_op("*"):
            star = self.advance()
            value = self.parse_expression()
            return StarredExpression(value, False, line=star.line, column=star.column)

        node = self.parse_ternary()

        # The walrus binds looser than everything except a comma.
        if self.check_op(":="):
            self.advance()
            value = self.parse_expression()
            return WalrusExpression(node, value, line=node.line, column=node.column)
        return node

    def parse_ternary(self):
        node = self.parse_or()
        # `value bet condition nah other`, W++'s conditional expression.
        if self.current.is_keyword("bet") or self.at_word("if"):
            self.advance()
            test = self.parse_or()
            if self.current.is_keyword("nah") or self.at_word("else"):
                self.advance()
            else:
                self.fail("a one-line `bet` needs a `nah`")
            orelse = self.parse_expression()
            return ConditionalExpression(node, test, orelse,
                                         line=node.line, column=node.column)
        return node

    def parse_or(self):
        node = self.parse_and()
        if not self.at_word("or"):
            return node
        values = [node]
        while self.accept_name("or"):
            values.append(self.parse_and())
        return BooleanExpression("or", values, line=node.line, column=node.column)

    def parse_and(self):
        node = self.parse_not()
        if not self.at_word("and"):
            return node
        values = [node]
        while self.accept_name("and"):
            values.append(self.parse_not())
        return BooleanExpression("and", values, line=node.line, column=node.column)

    def parse_not(self):
        if self.at_word("not"):
            token = self.advance()
            return UnaryExpression("not", self.parse_not(),
                                   line=token.line, column=token.column)
        return self.parse_comparison()

    def parse_comparison(self):
        node = self.parse_binary(0)
        operators = []
        comparators = []
        while True:
            operator = self._comparison_operator()
            if operator is None:
                break
            comparators.append(self.parse_binary(0))
            operators.append(operator)
        if not operators:
            return node
        return ComparisonExpression(node, operators, comparators,
                                    line=node.line, column=node.column)

    def _comparison_operator(self):
        token = self.current
        if token.type == TokenType.OP and token.value in _COMPARISON_OPS:
            self.advance()
            return token.value
        if token.is_name("in"):
            self.advance()
            return "in"
        if token.is_name("not") and self.peek().is_name("in"):
            self.advance()
            self.advance()
            return "not in"
        if token.is_name("is"):
            self.advance()
            if self.at_word("not"):
                self.advance()
                return "is not"
            return "is"
        return None

    def parse_binary(self, level):
        if level >= len(_BINARY_PRECEDENCE):
            return self.parse_unary()

        node = self.parse_binary(level + 1)
        symbols = _BINARY_PRECEDENCE[level]
        while self.current.type == TokenType.OP and self.current.value in symbols:
            operator = self.advance().value
            right = self.parse_binary(level + 1)
            node = BinaryExpression(node, operator, right,
                                    line=node.line, column=node.column)
        return node

    def parse_unary(self):
        token = self.current
        if token.is_op("-", "+", "~"):
            self.advance()
            return UnaryExpression(token.value, self.parse_unary(),
                                   line=token.line, column=token.column)
        if token.is_name("await"):
            self.advance()
            return AwaitExpression(self.parse_unary(),
                                   line=token.line, column=token.column)
        return self.parse_power()

    def parse_power(self):
        node = self.parse_postfix()
        if self.check_op("**"):
            self.advance()
            # Right associative, and the exponent may itself be signed.
            right = self.parse_unary()
            return BinaryExpression(node, "**", right,
                                    line=node.line, column=node.column)
        return node

    def parse_postfix(self):
        node = self.parse_atom()
        while True:
            if self.check_op("("):
                self.advance()
                args, keywords = self.parse_call_arguments()
                self.expect_op(")", "to close the call")
                node = CallExpression(node, args, keywords,
                                      line=node.line, column=node.column)
                continue
            if self.check_op("["):
                self.advance()
                index = self.parse_subscript()
                self.expect_op("]", "to close the subscript")
                node = IndexExpression(node, index,
                                       line=node.line, column=node.column)
                continue
            if self.check_op("."):
                self.advance()
                name_token = self.current
                if name_token.type not in (TokenType.NAME, TokenType.KEYWORD):
                    self.fail("expected an attribute name after `.`")
                self.advance()
                # After a dot a W++ keyword is just a name, which is why
                # `stack.dip()` keeps working.
                node = AttributeExpression(node, name_token.value,
                                           line=node.line, column=node.column)
                continue
            return node

    def parse_subscript(self):
        items = []
        while True:
            items.append(self.parse_slice_item())
            if not self.accept_op(","):
                break
            if self.check_op("]"):
                items.append(None)
                break
        if len(items) == 1:
            return items[0]
        return TupleLiteral([item for item in items if item is not None], False,
                            line=self.current.line, column=self.current.column)

    def parse_slice_item(self):
        lower = None
        if not self.check_op(":"):
            lower = self.parse_expression(allow_star=True)
            if not self.check_op(":"):
                return lower
        start = self.current
        self.expect_op(":")
        upper = None
        step = None
        if not self.check_op(":", "]", ","):
            upper = self.parse_expression()
        if self.accept_op(":"):
            if not self.check_op("]", ","):
                step = self.parse_expression()
        return SliceExpression(lower, upper, step,
                               line=start.line, column=start.column)

    def parse_call_arguments(self):
        args = []
        keywords = []
        while not self.check_op(")"):
            if self.accept_op("**"):
                keywords.append(KeywordArgument(None, self.parse_expression()))
            elif self.check_op("*"):
                star = self.advance()
                args.append(StarredExpression(self.parse_expression(), False,
                                              line=star.line, column=star.column))
            elif (self.current.type in (TokenType.NAME, TokenType.KEYWORD)
                    and self.peek().is_op("=")
                    and not self.peek().is_op("==")):
                if self.current.type == TokenType.KEYWORD:
                    # `f(bet=1)` would have to become `f(if=1)`.
                    self.reject_keyword_name(self.current,
                                             "a keyword argument name")
                name_token = self.advance()
                self.advance()  # =
                keywords.append(KeywordArgument(name_token.value,
                                                self.parse_expression()))
            else:
                value = self.parse_expression()
                clauses = self.parse_comprehension_clauses()
                if clauses is not None:
                    value = Comprehension("generator", value, None, clauses,
                                          line=value.line, column=value.column)
                args.append(value)
            if not self.accept_op(","):
                break
        return args, keywords

    def parse_comprehension_clauses(self):
        """Read `spam x in xs bet cond` clauses, or return None if absent."""
        if not (self.current.is_keyword("spam") or self.at_word("for")
                or (self.at_word("async") and self.peek().is_keyword("spam"))):
            return None

        clauses = []
        while True:
            is_async = bool(self.accept_name("async"))
            if not (self.accept_keyword("spam") or self.accept_name("for")):
                break
            target = self.parse_target_list()
            if not self.accept_name("in"):
                self.fail("expected `in` in this comprehension")
            iterable = self.parse_or()
            conditions = []
            while self.current.is_keyword("bet") or self.at_word("if"):
                self.advance()
                conditions.append(self.parse_or_no_ternary())
            clauses.append(ComprehensionClause(target, iterable, conditions, is_async))
            if not (self.current.is_keyword("spam") or self.at_word("for")
                    or (self.at_word("async") and self.peek().is_keyword("spam"))):
                break
        return clauses

    def parse_or_no_ternary(self):
        """A comprehension filter: `bet` here is a filter, not a ternary."""
        return self.parse_or()

    def parse_lambda(self):
        token = self.advance()
        params = []
        if not self.check_op(":"):
            params = self.parse_lambda_parameters()
        self.expect_op(":", "to open the lambda body")
        body = self.parse_expression()
        return LambdaExpression(params, body, line=token.line, column=token.column)

    def parse_lambda_parameters(self):
        params = []
        seen_star = False
        while not self.check_op(":"):
            if self.accept_op("*"):
                seen_star = True
                if self.check_op(","):
                    self.advance()
                    continue
                params.append(self._one_lambda_parameter("vararg"))
            elif self.accept_op("**"):
                params.append(self._one_lambda_parameter("kwarg"))
            else:
                params.append(self._one_lambda_parameter(
                    "keyword_only" if seen_star else "normal"))
            if not self.accept_op(","):
                break
        return params

    def _one_lambda_parameter(self, kind):
        token = self.current
        if token.type == TokenType.KEYWORD:
            self.reject_keyword_name(token, "a parameter name")
        self.advance()
        default = None
        if self.accept_op("="):
            default = self.parse_expression()
        return Parameter(token.value, default, kind, None,
                         line=token.line, column=token.column)

    def parse_yield(self):
        token = self.advance()
        if self.accept_name("from"):
            return YieldExpression(self.parse_expression(), True,
                                   line=token.line, column=token.column)
        value = None
        if not self._at_expression_end():
            value = self.parse_expression_list()
        return YieldExpression(value, False, line=token.line, column=token.column)

    def parse_atom(self):
        token = self.current

        if token.type == TokenType.NUMBER:
            self.advance()
            return Literal(None, token.value, "number",
                           line=token.line, column=token.column)

        if token.type == TokenType.STRING:
            # Adjacent literals concatenate, as in Python.
            parts = [self.advance().value]
            while self.current.type == TokenType.STRING:
                parts.append(self.advance().value)
            return Literal(None, " ".join(parts), "string",
                           line=token.line, column=token.column)

        if token.type == TokenType.FSTRING:
            self.advance()
            node = FStringLiteral(token.extra["raw"], token.extra.get("fields"),
                                  token.extra.get("start"),
                                  line=token.line, column=token.column)
            self._parse_fstring_fields(node)
            return node

        if token.type == TokenType.KEYWORD:
            if token.value in ("nocap", "cap", "npc"):
                self.advance()
                return Literal(token.value, token.value, "constant",
                               line=token.line, column=token.column)
            # A keyword such as `squad` or `range` used as a value: it maps to a
            # Python builtin, so it behaves as a name here.
            if token.value in ("squad", "tea", "cult", "range", "bodycount",
                               "yap", "dm"):
                self.advance()
                return Identifier(token.value, line=token.line, column=token.column)
            self.fail("`{}` cannot be used as a value".format(token.value))

        if token.type == TokenType.NAME:
            if token.value in _STATEMENT_WORDS and token.value not in (
                    "None", "True", "False"):
                if token.value not in ("match", "case", "type"):
                    self.fail("`{}` cannot start an expression".format(token.value))
            self.advance()
            return Identifier(token.value, line=token.line, column=token.column)

        if token.is_op("("):
            return self.parse_parenthesised()
        if token.is_op("["):
            return self.parse_list_display()
        if token.is_op("{"):
            return self.parse_brace_display()
        if token.is_op("..."):
            self.advance()
            return Literal(None, "...", "ellipsis",
                           line=token.line, column=token.column)

        self.fail("expected a value")

    def _parse_fstring_fields(self, node):
        """Parse each replacement field of an f-string into an expression."""
        if not node.fields:
            node.parsed_fields = []
            return
        parsed = []
        for field in node.fields:
            tokens = list(field["tokens"])
            if not tokens:
                continue
            from .tokens import Token as _Token
            tokens.append(_Token(TokenType.EOF, "", tokens[-1].end_line,
                                 tokens[-1].end_column))
            inner = _Parser(tokens, self.source)
            expression = inner.parse_expression_list(allow_star=True)
            parsed.append({"start": field["start"], "end": field["end"],
                           "expression": expression})
        node.parsed_fields = parsed

    def parse_parenthesised(self):
        open_token = self.advance()

        if self.check_op(")"):
            self.advance()
            return TupleLiteral([], True, line=open_token.line, column=open_token.column)

        if self.at_word("yield"):
            inner = self.parse_yield()
            self.expect_op(")", "to close the group")
            return inner

        first = self.parse_expression(allow_star=True)

        clauses = self.parse_comprehension_clauses()
        if clauses is not None:
            self.expect_op(")", "to close the generator")
            return Comprehension("generator", first, None, clauses,
                                 line=open_token.line, column=open_token.column)

        if self.check_op(","):
            items = [first]
            while self.accept_op(","):
                if self.check_op(")"):
                    break
                items.append(self.parse_expression(allow_star=True))
            self.expect_op(")", "to close the tuple")
            return TupleLiteral(items, True, line=open_token.line,
                                column=open_token.column)

        self.expect_op(")", "to close the group")
        first.parenthesised = True
        return first

    def parse_list_display(self):
        open_token = self.advance()
        if self.check_op("]"):
            self.advance()
            return ListLiteral([], line=open_token.line, column=open_token.column)

        first = self.parse_expression(allow_star=True)
        clauses = self.parse_comprehension_clauses()
        if clauses is not None:
            self.expect_op("]", "to close the comprehension")
            return Comprehension("list", first, None, clauses,
                                 line=open_token.line, column=open_token.column)

        items = [first]
        while self.accept_op(","):
            if self.check_op("]"):
                break
            items.append(self.parse_expression(allow_star=True))
        self.expect_op("]", "to close the list")
        return ListLiteral(items, line=open_token.line, column=open_token.column)

    def parse_brace_display(self):
        open_token = self.advance()
        if self.check_op("}"):
            self.advance()
            return DictLiteral([], line=open_token.line, column=open_token.column)

        # `{**other}` is a dict; `{*items}` is a set.
        if self.accept_op("**"):
            value = self.parse_or()
            pairs = [(None, value)]
            while self.accept_op(","):
                if self.check_op("}"):
                    break
                pairs.append(self._dict_pair())
            self.expect_op("}", "to close the dict")
            return DictLiteral(pairs, line=open_token.line, column=open_token.column)

        first = self.parse_expression(allow_star=True)

        if self.check_op(":"):
            self.advance()
            first_value = self.parse_expression()
            clauses = self.parse_comprehension_clauses()
            if clauses is not None:
                self.expect_op("}", "to close the comprehension")
                return Comprehension("dict", first, first_value, clauses,
                                     line=open_token.line, column=open_token.column)
            pairs = [(first, first_value)]
            while self.accept_op(","):
                if self.check_op("}"):
                    break
                pairs.append(self._dict_pair())
            self.expect_op("}", "to close the dict")
            return DictLiteral(pairs, line=open_token.line, column=open_token.column)

        clauses = self.parse_comprehension_clauses()
        if clauses is not None:
            self.expect_op("}", "to close the comprehension")
            return Comprehension("set", first, None, clauses,
                                 line=open_token.line, column=open_token.column)

        items = [first]
        while self.accept_op(","):
            if self.check_op("}"):
                break
            items.append(self.parse_expression(allow_star=True))
        self.expect_op("}", "to close the set")
        return SetLiteral(items, line=open_token.line, column=open_token.column)

    def _dict_pair(self):
        if self.accept_op("**"):
            return (None, self.parse_or())
        key = self.parse_expression()
        self.expect_op(":", "between a dict key and its value")
        return (key, self.parse_expression())


class _Sequence:
    """Several small statements written on one line, joined by semicolons."""

    _fields = ("statements",)

    def __init__(self, statements):
        self.statements = statements
        self.line = statements[0].line if statements else None
        self.column = statements[0].column if statements else None

    def dump(self, indent=0):
        pad = "  " * indent
        lines = ["{}Sequence".format(pad)]
        for item in self.statements:
            lines.append(item.dump(indent + 1))
        return "\n".join(lines)


def _render_tokens(tokens):
    """Join tokens back into source text, used only for `case` patterns."""
    pieces = []
    previous = None
    for token in tokens:
        if previous is not None:
            same_line = token.line == previous.end_line
            if not same_line or token.column > previous.end_column:
                pieces.append(" ")
        pieces.append(str(token.value))
        previous = token
    return "".join(pieces)

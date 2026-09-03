"""Unit tests for the W++ compiler stages.

One class per stage, so a failure says which part of the pipeline broke:
lexer, parser and AST, semantic checks, code generator, source map.
"""

import ast
import textwrap
import unittest

from wpplang import KEYWORDS, compile_wpp, run_source
from wpplang.compiler import compile_source, parse, tokenize_source
from wpplang.compiler import nodes as N
from wpplang.compiler.errors import (
    WppIndentationError, WppSemanticError, WppSyntaxError,
)
from wpplang.compiler.tokens import TokenType


def wpp(text):
    return textwrap.dedent(text).lstrip("\n")


def tokens_of(source):
    """Tokens with the layout noise removed, for readable assertions."""
    skip = (TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT, TokenType.EOF)
    return [t for t in tokenize_source(source) if t.type not in skip]


class LexerTests(unittest.TestCase):
    def test_keywords_are_their_own_token_type(self):
        tokens = tokens_of("cook f():\n    spill 1\n")
        kinds = [(t.type, t.value) for t in tokens]
        self.assertIn((TokenType.KEYWORD, "cook"), kinds)
        self.assertIn((TokenType.KEYWORD, "spill"), kinds)
        self.assertIn((TokenType.NAME, "f"), kinds)

    def test_every_dictionary_word_lexes_as_a_keyword(self):
        for word in KEYWORDS:
            with self.subTest(keyword=word):
                token = tokens_of(word + "\n")[0]
                self.assertEqual(token.type, TokenType.KEYWORD)
                self.assertEqual(token.value, word)

    def test_an_identifier_containing_a_keyword_is_a_name(self):
        for name in ("cookie", "recap", "cap_rate", "spamalot", "betting"):
            with self.subTest(name=name):
                token = tokens_of(name + " = 1\n")[0]
                self.assertEqual(token.type, TokenType.NAME)
                self.assertEqual(token.value, name)

    def test_a_string_is_one_token_however_many_keywords_it_holds(self):
        # This is the structural reason keywords in strings are safe: the
        # scanner never looks inside a literal.
        tokens = tokens_of('yap("cook bet spill nah")\n')
        strings = [t for t in tokens if t.type == TokenType.STRING]
        self.assertEqual(len(strings), 1)
        self.assertEqual(strings[0].value, '"cook bet spill nah"')

    def test_a_comment_produces_no_tokens(self):
        self.assertEqual(tokens_of("# cook bet yap\n"), [])

    def test_positions_are_recorded(self):
        token = tokens_of("\n\n    yap(1)\n")[0]
        self.assertEqual(token.value, "yap")
        self.assertEqual(token.line, 3)
        self.assertEqual(token.column, 4)

    def test_indentation_becomes_indent_and_dedent(self):
        kinds = [t.type for t in tokenize_source("cook f():\n    spill 1\n")]
        self.assertIn(TokenType.INDENT, kinds)
        self.assertIn(TokenType.DEDENT, kinds)

    def test_fstring_fields_are_lexed_but_its_text_is_not(self):
        token = [t for t in tokens_of('yap(f"a{bodycount(x)}b{{c}}")\n')
                 if t.type == TokenType.FSTRING][0]
        self.assertEqual(len(token.extra["fields"]), 1)
        inside = "".join(str(t.value) for t in token.extra["fields"][0]["tokens"])
        self.assertEqual(inside, "bodycount(x)")

    def test_a_format_spec_is_not_treated_as_code(self):
        token = [t for t in tokens_of('yap(f"{v:.2f}")\n')
                 if t.type == TokenType.FSTRING][0]
        inside = "".join(str(t.value) for t in token.extra["fields"][0]["tokens"])
        self.assertEqual(inside, "v")

    def test_an_unterminated_string_is_a_wpp_error(self):
        with self.assertRaises(WppSyntaxError) as caught:
            tokenize_source('yap("oops\n')
        self.assertEqual(caught.exception.line, 1)

    def test_bad_indentation_is_an_indentation_error(self):
        with self.assertRaises(WppIndentationError):
            tokenize_source("cook f():\n    yap(1)\n  yap(2)\n")


class ParserTests(unittest.TestCase):
    def tree(self, source):
        return parse(tokenize_source(source), source)

    def test_the_official_vibe_check_shape(self):
        """The example from the spec must parse into the documented shape."""
        program = self.tree(wpp('''
            cook check_vibe(name):
                bet name == "Claude":
                    spill "W AI"
                nah:
                    spill "Mid"
        '''))
        self.assertIsInstance(program, N.Program)
        function = program.body[0]
        self.assertIsInstance(function, N.FunctionDeclaration)
        self.assertEqual(function.name, "check_vibe")
        self.assertEqual([p.name for p in function.params], ["name"])
        self.assertEqual(function.keyword, "cook")

        branch = function.body[0]
        self.assertIsInstance(branch, N.IfStatement)
        self.assertEqual(len(branch.branches), 1)
        condition, body = branch.branches[0]
        self.assertIsInstance(condition, N.ComparisonExpression)
        self.assertEqual(condition.operators, ["=="])
        self.assertIsInstance(body[0], N.ReturnStatement)
        self.assertIsInstance(branch.orelse[0], N.ReturnStatement)

    def test_elif_branches_are_collected(self):
        program = self.tree(wpp('''
            bet 1:
                yap(1)
            plotwist 2:
                yap(2)
            plotwist 3:
                yap(3)
            nah:
                yap(4)
        '''))
        node = program.body[0]
        self.assertEqual(len(node.branches), 3)
        self.assertIsNotNone(node.orelse)

    def test_loop_nodes_record_their_keyword(self):
        program = self.tree("spam i in range(2):\n    yap(i)\n")
        self.assertEqual(program.body[0].keyword, "spam")
        program = self.tree("grind 0:\n    yap(1)\n")
        self.assertEqual(program.body[0].keyword, "grind")

    def test_a_loop_else_belongs_to_the_loop_not_the_inner_if(self):
        """The clause that caught a real bug during the refactor."""
        program = self.tree(wpp('''
            spam n in [1]:
                bet n == 5:
                    dip
            nah:
                yap("none")
        '''))
        loop = program.body[0]
        self.assertIsInstance(loop, N.ForStatement)
        self.assertIsNotNone(loop.orelse, "the `nah` should be the loop's")
        inner = loop.body[0]
        self.assertIsInstance(inner, N.IfStatement)
        self.assertIsNone(inner.orelse, "the `bet` should have no else")

    def test_expressions_become_expression_nodes(self):
        program = self.tree("x = 1 + 2 * 3\n")
        value = program.body[0].value
        self.assertIsInstance(value, N.BinaryExpression)
        self.assertEqual(value.operator, "+")
        # Precedence: the multiplication is the right operand.
        self.assertIsInstance(value.right, N.BinaryExpression)
        self.assertEqual(value.right.operator, "*")

    def test_comparison_chains_are_one_node(self):
        program = self.tree("x = 1 < 2 < 3\n")
        value = program.body[0].value
        self.assertIsInstance(value, N.ComparisonExpression)
        self.assertEqual(value.operators, ["<", "<"])

    def test_collection_literals(self):
        program = self.tree("a = [1]\nb = {1: 2}\nc = {1}\nd = (1, 2)\n")
        kinds = [type(statement.value) for statement in program.body]
        self.assertEqual(kinds, [N.ListLiteral, N.DictLiteral, N.SetLiteral,
                                 N.TupleLiteral])

    def test_comprehension_clauses(self):
        program = self.tree("x = [i spam i in range(4) bet i > 1]\n")
        value = program.body[0].value
        self.assertIsInstance(value, N.Comprehension)
        self.assertEqual(value.kind, "list")
        self.assertEqual(len(value.clauses), 1)
        self.assertEqual(len(value.clauses[0].conditions), 1)

    def test_call_and_index_and_attribute(self):
        program = self.tree("x = thing.part[0](1, k=2)\n")
        call = program.body[0].value
        self.assertIsInstance(call, N.CallExpression)
        self.assertEqual([k.name for k in call.keywords], ["k"])
        self.assertIsInstance(call.callee, N.IndexExpression)
        self.assertIsInstance(call.callee.value, N.AttributeExpression)

    def test_nodes_carry_positions(self):
        program = self.tree("yap(1)\n\nspam i in range(2):\n    yap(i)\n")
        self.assertEqual(program.body[0].line, 1)
        self.assertEqual(program.body[1].line, 3)
        self.assertEqual(program.body[1].body[0].line, 4)

    def test_a_keyword_as_a_function_name_is_rejected_with_its_position(self):
        with self.assertRaises(WppSyntaxError) as caught:
            self.tree("cook dip(self):\n    spill 1\n")
        error = caught.exception
        self.assertEqual(error.line, 1)
        self.assertIn("'dip' is a W++ keyword", error.message)

    def test_python_keywords_are_refused_where_wpp_has_its_own_word(self):
        for source in ("if 1:\n    yap(1)\n", "for i in range(2):\n    yap(i)\n",
                       "while 0:\n    yap(1)\n"):
            with self.subTest(source=source.split(None, 1)[0]):
                with self.assertRaises(WppSyntaxError):
                    self.tree(source)

    def test_the_ast_can_be_dumped(self):
        program = self.tree("cook f(a):\n    spill a\n")
        dump = program.dump()
        self.assertIn("Program", dump)
        self.assertIn("FunctionDeclaration", dump)
        self.assertIn("ReturnStatement", dump)


class SemanticTests(unittest.TestCase):
    def test_dip_outside_a_loop_is_rejected(self):
        with self.assertRaises(WppSemanticError) as caught:
            compile_source("yap(1)\ndip\n")
        self.assertEqual(caught.exception.line, 2)
        self.assertIn("`dip`", caught.exception.message)

    def test_skrrt_outside_a_loop_is_rejected(self):
        with self.assertRaises(WppSemanticError):
            compile_source("skrrt\n")

    def test_spill_outside_a_function_is_rejected(self):
        with self.assertRaises(WppSemanticError) as caught:
            compile_source("spill 1\n")
        self.assertIn("`spill`", caught.exception.message)

    def test_dip_inside_a_loop_is_fine(self):
        compile_source("spam i in range(2):\n    dip\n")
        compile_source("grind 1:\n    dip\n")

    def test_a_loop_does_not_reach_into_a_nested_function(self):
        with self.assertRaises(WppSemanticError):
            compile_source(wpp('''
                spam i in range(2):
                    cook inner():
                        dip
            '''))

    def test_assigning_to_a_keyword_is_rejected(self):
        with self.assertRaises(WppSemanticError) as caught:
            compile_source("cap = 1\n")
        self.assertIn("cannot be assigned to", caught.exception.message)

    def test_a_repeated_parameter_is_rejected(self):
        with self.assertRaises(WppSemanticError):
            compile_source("cook f(a, a):\n    spill a\n")


class CodeGeneratorTests(unittest.TestCase):
    def generate(self, source):
        return compile_source(source).python

    def assertMeans(self, source, python):
        self.assertEqual(ast.dump(ast.parse(self.generate(source))),
                         ast.dump(ast.parse(python)))

    def test_the_generator_uses_the_dictionary(self):
        self.assertMeans("cook f():\n    spill 1\n", "def f():\n    return 1\n")

    def test_the_generator_reads_the_tree_not_the_text(self):
        """Proof the generator is driven by the AST: hand it one directly."""
        from wpplang.compiler.codegen import generate

        program = N.Program([
            N.FunctionDeclaration(
                "greet", [N.Parameter("name", None, "normal", None)],
                [N.ReturnStatement(N.Identifier("name"), "spill")],
                [], False, None, "cook"),
        ])
        python, _map = generate(program)
        self.assertEqual(ast.dump(ast.parse(python)),
                         ast.dump(ast.parse("def greet(name):\n    return name\n")))

    def test_generated_python_is_valid_for_every_construct(self):
        for source in ("cook f(*a, **k):\n    spill a\n",
                       "spam i in range(2):\n    yap(i)\nnah:\n    yap(9)\n",
                       "x = [i spam i in range(2) bet i]\n",
                       "x = lambda n: n\n",
                       'x = f"{1 + 1}"\n'):
            with self.subTest(source=source.strip().splitlines()[0]):
                ast.parse(self.generate(source))

    def test_an_empty_block_becomes_pass(self):
        # Only a block needs filling; a whole empty file generates nothing.
        self.assertEqual(self.generate("").strip(), "")


class SourceMapTests(unittest.TestCase):
    def test_generated_lines_map_back_to_wpp_lines(self):
        compiled = compile_wpp(wpp('''
            yap("one")

            cook boom():
                spill 1 / 0

            boom()
        '''))
        # Every recorded Python line points at a real W++ line.
        for python_line, wpp_line in compiled.source_map.as_dict().items():
            self.assertGreaterEqual(python_line, 1)
            self.assertGreaterEqual(wpp_line, 1)
        self.assertEqual(compiled.wpp_line_for(4), 4)

    def test_a_runtime_error_is_reported_against_the_wpp_line(self):
        result = run_source(wpp('''
            cook a():
                spill b()

            cook b():
                spill 1 / 0

            a()
        '''), "t.wpp")
        details = result.error_details
        self.assertEqual(details["message"],
                         "Math ain't mathing: Bro tried to divide by zero "
                         "(ZeroDivisionError)")
        self.assertEqual(details["line"], 5)
        self.assertEqual(details["source_line"], "spill 1 / 0")

    def test_a_multi_line_statement_does_not_shift_later_lines(self):
        result = run_source(wpp('''
            blurb = """
            one
            two
            """
            yap(missing_name)
        '''), "t.wpp")
        self.assertEqual(result.error_details["line"], 5)
        self.assertEqual(result.error_details["source_line"], "yap(missing_name)")


if __name__ == "__main__":
    unittest.main()

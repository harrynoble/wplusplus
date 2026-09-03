"""Check that every W++ example in the learning guide still works.

docs/build_guide.py runs each example while writing the PDF, so a broken
example would already stop the build.  This test runs the same examples
without needing reportlab installed, so a change to the language cannot
quietly invalidate the guide.
"""

import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDER = os.path.join(ROOT, "docs", "build_guide.py")


def load_builder():
    """Import docs/build_guide.py, or return None if reportlab is missing."""
    spec = importlib.util.spec_from_file_location("wpp_guide_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError:
        return None
    return module


class GuideExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(BUILDER):
            raise unittest.SkipTest("the guide builder is not present")
        cls.builder = load_builder()
        if cls.builder is None:
            raise unittest.SkipTest("reportlab is not installed")

    def test_every_example_behaves_as_the_guide_says(self):
        builder = self.builder
        builder.PROBLEMS.clear()

        examples = 0
        for block in builder.build_content():
            if not isinstance(block, tuple) or block[0] != "code":
                continue
            _, source, answers, expect_error, _caption, run_it = block
            if not run_it:
                continue
            examples += 1
            # run() records anything unexpected in PROBLEMS.
            builder.run(source, answers=answers, expect_error=expect_error,
                        label=source.splitlines()[0][:52])

        self.assertGreater(examples, 60, "expected the guide to be substantial")
        self.assertEqual(
            builder.PROBLEMS, [],
            "the guide contains examples that no longer behave as printed:\n"
            + "\n".join(builder.PROBLEMS))

    def test_no_example_is_too_wide_for_the_page(self):
        builder = self.builder
        builder.PROBLEMS.clear()

        for block in builder.build_content():
            if not isinstance(block, tuple):
                continue
            if block[0] == "code":
                builder.check_width(block[1], "an example")
            elif block[0] == "snippet":
                builder.check_width(block[1], "a snippet")
            elif block[0] == "shell":
                builder.check_width(block[1], "a shell command")

        self.assertEqual(
            builder.PROBLEMS, [],
            "content too wide for the code box:\n" + "\n".join(builder.PROBLEMS))


if __name__ == "__main__":
    unittest.main()

"""The committed browser bundle must match the package it was built from.

playground/static/wpp-sources.json carries the compiler's Python sources so the
browser build can run them under Pyodide.  It is generated and committed, which
is what lets the playground deploy as static files with no build step - and
also what lets it drift.  These tests make drift a test failure.
"""

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "playground", "static", "wpp-sources.json")
STATIC = os.path.join(ROOT, "playground", "static")


def load_bundle():
    with open(BUNDLE, encoding="utf-8") as handle:
        return json.load(handle)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.bundle = load_bundle()

    def test_every_module_matches_the_file_on_disk(self):
        for relative, text in self.bundle["modules"].items():
            path = os.path.join(ROOT, relative.replace("/", os.sep))
            with self.subTest(module=relative):
                self.assertTrue(os.path.isfile(path), relative + " is missing")
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(
                        handle.read(), text,
                        relative + " has changed since the bundle was built; "
                        "run: python tools/build_web_bundle.py")

    def test_the_whole_compiler_is_bundled(self):
        compiler = os.path.join(ROOT, "wpplang", "compiler")
        expected = {
            "wpplang/compiler/" + name
            for name in os.listdir(compiler) if name.endswith(".py")
        }
        self.assertTrue(expected <= set(self.bundle["modules"]),
                        "missing from the bundle: %s"
                        % sorted(expected - set(self.bundle["modules"])))

    def test_the_language_package_is_bundled(self):
        for name in ("__init__.py", "keywords.py", "errors.py", "runner.py",
                     "translator.py"):
            self.assertIn("wpplang/" + name, self.bundle["modules"])

    def test_sound_is_left_out(self):
        # It plays audio through the operating system; nothing on the browser
        # path imports it, and it would only bloat the download.
        self.assertNotIn("wpplang/sound.py", self.bundle["modules"])

    def test_the_reference_payload_matches_the_package(self):
        from wpplang import CATEGORIES, KEYWORDS, SKILL_ISSUES, __version__

        reference = self.bundle["reference"]
        self.assertEqual(reference["keywords"], KEYWORDS)
        self.assertEqual(reference["categories"], CATEGORIES)
        self.assertEqual(reference["skillIssues"], SKILL_ISSUES)
        self.assertEqual(reference["version"], __version__)
        self.assertEqual(self.bundle["version"], __version__)

    def test_the_examples_match_the_files(self):
        for example in self.bundle["examples"]:
            path = os.path.join(ROOT, "examples", example["id"] + ".wpp")
            with self.subTest(example=example["id"]):
                self.assertTrue(os.path.isfile(path))
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), example["source"])

    def test_the_official_examples_are_offered(self):
        names = [example["name"] for example in self.bundle["examples"]]
        for required in ("Hello World", "Vibe Check", "FizzBuzz"):
            self.assertIn(required, names)

    def test_the_bundled_compiler_actually_works(self):
        """Compile a program using only the bundled text, not the package.

        This is what the browser does: read the sources out of the bundle and
        import them. If the bundle were incomplete this would fail.
        """
        import sys
        import tempfile

        with tempfile.TemporaryDirectory(prefix="wpp-bundle-") as folder:
            for relative, text in self.bundle["modules"].items():
                path = os.path.join(folder, relative.replace("/", os.sep))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(text)

            saved_path = list(sys.path)
            saved_modules = {name: module for name, module in sys.modules.items()
                             if name.startswith("wpplang")}
            for name in list(saved_modules):
                del sys.modules[name]
            sys.path.insert(0, folder)
            try:
                import wpplang as fresh
                self.assertEqual(
                    os.path.dirname(os.path.abspath(fresh.__file__)),
                    os.path.join(folder, "wpplang"))
                python = fresh.translate('yap("from the bundle")\n')
                self.assertIn('print("from the bundle")', python)
            finally:
                sys.path[:] = saved_path
                for name in [n for n in sys.modules if n.startswith("wpplang")]:
                    del sys.modules[name]
                sys.modules.update(saved_modules)


class StaticSiteTests(unittest.TestCase):
    """What a static host needs to serve."""

    def test_every_asset_the_page_needs_is_present(self):
        for name in ("index.html", "app.css", "app.js", "engine.js",
                     "wpp-worker.js", "wpp-sources.json", "favicon.svg",
                     "favicon.ico"):
            with self.subTest(asset=name):
                self.assertTrue(os.path.isfile(os.path.join(STATIC, name)), name)

    def test_the_page_loads_the_engine_before_the_app(self):
        with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as handle:
            page = handle.read()
        self.assertLess(page.index("engine.js"), page.index("app.js"))

    def test_the_app_does_not_call_the_api_directly(self):
        """Every request goes through the engine, so both builds work."""
        with open(os.path.join(STATIC, "app.js"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertNotIn("fetch('/api", script)
        self.assertNotIn("EventSource(", script)

    def test_vercel_config_points_at_the_static_directory(self):
        path = os.path.join(ROOT, "vercel.json")
        self.assertTrue(os.path.isfile(path), "vercel.json is missing")
        with open(path, encoding="utf-8") as handle:
            config = json.load(handle)
        self.assertEqual(config["outputDirectory"], "playground/static")


if __name__ == "__main__":
    unittest.main()

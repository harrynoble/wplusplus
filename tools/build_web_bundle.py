"""Bundle the W++ compiler into a static asset for the browser build.

The playground can run W++ two ways:

* locally, against `playground/server.py`, which executes each program in a
  child process;
* in the browser, with the same `wpplang` package running under Pyodide
  (CPython compiled to WebAssembly).

The browser build needs the Python sources as a static file it can fetch, so
this script writes them into playground/static/wpp-sources.json.  Running it
here rather than at deploy time means the hosted site is pure static files with
no build step - which is what makes it deployable anywhere, Vercel included.

    python tools/build_web_bundle.py

tests/test_web_bundle.py checks the committed bundle still matches the package,
so it cannot quietly go stale.
"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATIC = os.path.join(ROOT, "playground", "static")
TARGET = os.path.join(STATIC, "wpp-sources.json")

# The error sound lives at the repository root, where the CLI and the local
# server read it from.  A static host only serves playground/static, so it has
# to be copied in - otherwise the deployed page asks for a file that is not
# there and fails silently, which is exactly what happened.
ERROR_SOUND = os.path.join(ROOT, "audio", "fah.mp3")
SOUND_COPY = os.path.join(STATIC, "audio", "fah.mp3")

# The modules the browser needs.  `sound.py` is left out on purpose: it plays
# audio through the operating system and nothing on the browser path imports it.
MODULES = [
    "wpplang/__init__.py",
    "wpplang/keywords.py",
    "wpplang/errors.py",
    "wpplang/translator.py",
    "wpplang/runner.py",
    "wpplang/compiler/__init__.py",
    "wpplang/compiler/tokens.py",
    "wpplang/compiler/errors.py",
    "wpplang/compiler/lexer.py",
    "wpplang/compiler/nodes.py",
    "wpplang/compiler/parser.py",
    "wpplang/compiler/semantic.py",
    "wpplang/compiler/codegen.py",
]

EXAMPLES_DIR = os.path.join(ROOT, "examples")

# Which examples the menu offers, matching playground/server.py so the two
# builds show the same list.
EXAMPLES = [
    ("hello", "Hello World", "hello.wpp"),
    ("vibe_check", "Vibe Check", "vibe_check.wpp"),
    ("fizzbuzz", "FizzBuzz", "fizzbuzz.wpp"),
    ("collections", "Collections", "collections.wpp"),
    ("keyword_tour", "Keyword Tour", "keyword_tour.wpp"),
    ("oops", "Skill Issue", "oops.wpp"),
]


def build():
    """Collect everything the browser build needs."""
    sys.path.insert(0, ROOT)
    from wpplang import CATEGORIES, KEYWORDS, SKILL_ISSUES, __version__

    modules = {}
    for relative in MODULES:
        path = os.path.join(ROOT, relative.replace("/", os.sep))
        with open(path, "r", encoding="utf-8") as handle:
            modules[relative] = handle.read()

    examples = []
    for identifier, name, filename in EXAMPLES:
        path = os.path.join(EXAMPLES_DIR, filename)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            examples.append({"id": identifier, "name": name,
                             "source": handle.read()})

    return {
        "version": __version__,
        "modules": modules,
        "examples": examples,
        # The same payload /api/reference serves, so the docs drawer works
        # identically in both builds.
        "reference": {
            "version": __version__,
            "keywords": KEYWORDS,
            "categories": CATEGORIES,
            "skillIssues": SKILL_ISSUES,
        },
    }


def copy_error_sound():
    """Put the error sound where a static host can serve it.

    The CLI and the local server read audio/fah.mp3 from the repository root,
    but a static host only serves playground/static - so without this copy the
    deployed page requests a file that is not there and stays silent, which is
    exactly what happened on the first deployment.
    """
    if not os.path.isfile(ERROR_SOUND):
        print("  no audio/fah.mp3 to copy; the deployed page will stay quiet")
        return None
    os.makedirs(os.path.dirname(SOUND_COPY), exist_ok=True)
    shutil.copyfile(ERROR_SOUND, SOUND_COPY)
    return SOUND_COPY


def main():
    bundle = build()
    text = json.dumps(bundle, indent=1, sort_keys=True) + "\n"
    with open(TARGET, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    print("wrote %s" % TARGET)
    print("  %d modules, %d examples, %.0f KB"
          % (len(bundle["modules"]), len(bundle["examples"]),
             len(text.encode("utf-8")) / 1024.0))

    copied = copy_error_sound()
    if copied:
        print("copied %s (%.0f KB)"
              % (copied, os.path.getsize(copied) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

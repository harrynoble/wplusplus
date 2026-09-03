# W++

**A Turing-complete, dynamically-typed programming language built on Python semantics,
with the boring syntax replaced by Gen Z slang.** Maximum vibes, minimal skill issues.

```wpp
cook fizzbuzz(limit):
    spam i in range(1, limit + 1):
        bet i % 15 == 0:
            yap("FizzBuzz")
        plotwist i % 3 == 0:
            yap("Fizz")
        plotwist i % 5 == 0:
            yap("Buzz")
        nah:
            yap(i)

fizzbuzz(15)
```

## How W++ works

W++ is Python with a different vocabulary. A W++ program is translated into Python
source and then executed by the Python you already have installed:

```
   your_program.wpp
        |
        v
   keyword translation      (wpplang/translator.py)
        |
        v
   Python source            (see it with --emit)
        |
        v
   compile() + exec()       (wpplang/runner.py)
        |
        v
   output, or a Skill Issue (wpplang/errors.py)
```

Two rules make the translation safe:

1. **Keywords are matched as whole words**, using regex word boundaries. `cookie`
   stays `cookie`; only a standalone `cook` becomes `def`.
2. **String literals and comments are copied through verbatim**, so
   `yap("cook dinner")` prints `cook dinner` rather than `def dinner`.

The translator never adds or removes lines, so line 12 of the generated Python is
always line 12 of your `.wpp` file. That is what lets error messages point at your
original source.

## Setup

No dependencies, no build step. You need **Python 3.8+** and the standard library.

```bash
git clone https://github.com/harrynoble/wplusplus.git
cd wplusplus
```

## Running a W++ file

```bash
python wpp.py examples/fizzbuzz.wpp
```

| Command | What it does |
| --- | --- |
| `python wpp.py FILE.wpp` | Translate and run a W++ program |
| `python wpp.py --emit FILE.wpp` | Print the generated Python instead of running it |
| `python wpp.py --keywords` | Print the Official Dictionary |
| `python wpp.py --version` | Print the W++ version |

Exit codes: `0` success, `1` skill issue, `2` bad usage (missing file), `130` Ctrl-C.

## The playground

A local web playground with a code editor and an integrated output panel:

```bash
python playground/server.py
```

It opens http://127.0.0.1:8000. Pick a program from the Examples menu, press
**Run** (or Ctrl+Enter), and the output appears beside the editor.

**Input is interactive.** When a program calls `dm()`, the prompt is printed in
the output panel and a caret appears right after it - you type your answer there
and press Enter, exactly like a terminal. A program can ask as many times as it
likes, in a loop if it wants; each `dm()` waits for its own line. **Stop** ends a
run that is still going.

A run is a *session*, because a program can pause half way through to ask a
question:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/run` | start a program, returns a session id |
| `GET /api/stream?session=ID` | server-sent events: output, prompts, result |
| `POST /api/input` | one line of input for a waiting `dm()` |
| `POST /api/stop` | end the run |
| `GET /api/reference` | the keyword and Skill Issue tables |
| `GET /api/examples` | the programs in `examples/` |

Every run happens in a fresh child process, so nothing leaks between runs. The
worker reports output *and* prompts on a single ordered channel, which is what
guarantees the caret is never drawn above the text that asked for it.

Runs have a **10-second budget, measured in time actually spent running** - time
sitting at a prompt does not count, so you can take as long as you like to
answer while a runaway `grind` loop is still stopped after ten seconds. The
reported duration is compute time for the same reason.

The editor is Monaco when it can be reached, and a small built-in editor
otherwise, so the playground still works offline.

`python playground/server.py --port 9000 --no-browser` changes the port and
skips opening a browser.

> The playground executes the code it is given. It binds to `127.0.0.1` so it is
> reachable only from your machine - do not expose it to a network.

## The Official Dictionary

| W++ | Python | Category |
| --- | --- | --- |
| `cook` | `def` | Function declaration |
| `spill` | `return` | Return statement |
| `yap` | `print` | Console output |
| `dm` | `input` | User input |
| `bodycount` | `len` | Length / size |
| `bet` | `if` | Primary conditional |
| `plotwist` | `elif` | Secondary conditional |
| `nah` | `else` | Fallback conditional |
| `spam` | `for` | Iteration |
| `grind` | `while` | Looping |
| `dip` | `break` | Exit loop |
| `skrrt` | `continue` | Skip iteration |
| `nocap` | `True` | Boolean true |
| `cap` | `False` | Boolean false |
| `npc` | `None` | Null value |
| `squad` | `list` | Array / list |
| `tea` | `dict` | Dictionary / map |
| `cult` | `set` | Unique set |
| `range` | `range` | Sequence generator |

## Supported syntax

Everything in the dictionary above, plus **all ordinary Python syntax**, because the
translated program is just Python:

- Functions (`cook`), returns (`spill`), default arguments, recursion
- Conditionals (`bet` / `plotwist` / `nah`), including nesting
- Loops (`spam`, `grind`) with `dip` and `skrrt`
- Lists, dicts, sets — via `squad` / `tea` / `cult` or plain `[]`, `{}` literals
- Indexing, slicing, comprehensions, arithmetic and modulo
- Booleans (`nocap` / `cap`), `npc`, strings, f-strings, comments
- `import`, classes, exceptions, and the rest of the standard library

Inside an f-string, the `{...}` fields are code and get translated; the literal text
does not. `yap(f"total: {bodycount(squad_goals)}")` works as you would expect.

## Example program

```wpp
cook check_vibe(name):
    bet name == "Claude":
        spill "W AI"
    nah:
        spill "Mid"

username = dm("Who are you? ")
yap("Vibe check: ", check_vibe(username))
```

```bash
$ python wpp.py examples/vibe_check.wpp
Who are you? Claude
Vibe check:  W AI
```

More in [`examples/`](examples/): `hello.wpp`, `vibe_check.wpp`, `fizzbuzz.wpp`,
`collections.wpp`, `oops.wpp`.

[`examples/keyword_tour.wpp`](examples/keyword_tour.wpp) exercises **every**
keyword in the dictionary in one program, and a test asserts that it stays that
way - add a keyword to `wpplang/keywords.py` without using it there and the
suite fails.

## Error handling — the Skill Issue Protocol

Python tracebacks are intercepted and re-presented in W++ terms, with the file, the
line number and the offending source line:

```
$ python wpp.py examples/oops.wpp
about to fumble
🚨 Bro is making up words now (NameError)
   where: examples/oops.wpp, line 3
      3 | yap(undefined_thing)
   details: name 'undefined_thing' is not defined
```

(The report goes to stderr, so it can interleave with program output on a terminal.)

| Python exception | W++ message |
| --- | --- |
| `SyntaxError` | 🚨 Negative Aura: Bro forgot how to type (SyntaxError) |
| `NameError` | 🚨 Bro is making up words now (NameError) |
| `TypeError` | 🚨 Oil up bro, you can't combine those (TypeError) |
| `IndexError` | 🚨 Blud thinks he has more items than he does (IndexError) |
| `ZeroDivisionError` | 🚨 Bro just broke the matrix (ZeroDivisionError) |
| `IndentationError` | 🚨 Your spaces are looking a little sus (IndentationError) |
| `KeyboardInterrupt` | 🚨 Go touch grass, you've been looping forever (KeyboardInterrupt) |

Any exception outside this table is reported as
`🚨 Unspecified skill issue (ExceptionName)` with the same file/line context — you
never get a raw Python traceback.

## Tests

```bash
python -m unittest discover -s tests -t .
```

Covers every keyword translation, word-boundary and string-literal safety,
expressions, functions, conditionals, loops, collections, I/O, exit codes, every
Skill Issue message, the official spec examples run end to end, and the
playground API - interactive `dm()` prompts, several prompts in a row, prompts
inside a loop, the compute budget, Stop, and child-process cleanup.

## Project layout

```
wpp.py                  CLI entry point
wpplang/keywords.py     the Official Dictionary (single source of truth)
wpplang/translator.py   W++ -> Python source translation
wpplang/runner.py       compile + execute, exit codes
wpplang/errors.py       the Skill Issue Protocol
playground/server.py    local web playground (stdlib HTTP server)
playground/_worker.py   one child process per playground run
playground/static/      the playground front end
examples/               runnable W++ programs
tests/                  automated test suite
```

To add a keyword, add one line to `wpplang/keywords.py`. Everything else follows.

## Current limitations

- **W++ keywords are reserved words.** You cannot use one as an identifier or a
  keyword-argument name: `tea(cap=1)` translates to `dict(False=1)` and fails, the
  same way `dict(if=1)` fails in Python. Names that merely *contain* a keyword
  (`cookie`, `cap_rate`, `bet_size`) are fine.
- **Python keywords are not aliased.** `and`, `or`, `not`, `in`, `is`, `import`,
  `class`, `try`/`except`, `lambda` and friends are written the Python way; the spec
  only defines the 19 words above.
- **The translator is not a full Python parser.** It is a literal-aware regex pass.
  It understands strings (single, double, triple, raw, byte, f-strings) and comments,
  which covers real programs, but it does not build a syntax tree.
- **Errors are reported one at a time** — the first failure stops the program, as in
  Python.
- **No REPL** and no `.wpp` module imports: a program is a single file.
- **The playground is a local development tool**, not a hosted sandbox. It runs
  programs as your user account with only a time limit, so it belongs on your
  own machine and nowhere else.

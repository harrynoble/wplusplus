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

W++ has its own language frontend. Source is tokenized, parsed into a **W++
AST**, checked, and only then translated into Python by a dedicated backend.
Python is the execution target; it is not what W++ *is*.

```
   your_program.wpp
        |
        v
   Lexer                 wpplang/compiler/lexer.py
        |                 W++ tokens, each with a line and a column
        v
   Parser                wpplang/compiler/parser.py
        |                 recursive descent + precedence climbing
        v
   W++ AST               wpplang/compiler/nodes.py
        |                 FunctionDeclaration, IfStatement, ForStatement, ...
        v
   Semantic validation   wpplang/compiler/semantic.py
        |                 `dip` inside a loop? `spill` inside a `cook`?
        v
   Python code generator wpplang/compiler/codegen.py
        |                 walks the tree; emits Python + a W++ line map
        v
   Python runtime        wpplang/runner.py
        |
        v
   output, or a Skill Issue reported against your W++ line
```

Each stage has one job, and you can look at any of them:

```bash
python wpp.py --tokens my_program.wpp   # what the lexer saw
python wpp.py --ast    my_program.wpp   # the tree the parser built
python wpp.py --emit   my_program.wpp   # the Python the backend wrote
```

### Why this is not find-and-replace

*"Isn't W++ just renamed Python?"* W++ targets Python for execution, but it has
its own frontend: source is tokenized and parsed into a W++ AST, validated, and
translated by a separate backend. Two consequences you can check yourself:

- **A keyword inside a string is never a keyword.** The lexer hands back the
  whole literal as one token, so `yap("cook bet")` cannot become
  `print("def if")` — not because a regular expression was written carefully,
  but because nothing ever looks inside the string. Run `--tokens` and you will
  see one `STRING` token.
- **Errors talk about W++.** The AST carries a line and column on every node,
  and the code generator records which W++ line produced each Python line, so a
  failure names your line rather than a line in generated code you never saw.

W++'s grammar *is* Python's grammar with nineteen renamed words, so the parser
follows Python's statement forms and the lexer delegates character scanning to
Python's keyword-agnostic `tokenize`. What makes the frontend W++'s own is that
it recognises `bet`, `plotwist`, `nah`, `spam`, `grind`, `cook`, `spill`, `dip`
and `skrrt`, records which W++ word opened each construct, and enforces W++'s
own rules.

W++ does **not** have its own runtime, and it does not compile to machine code.
Python runs the result.

### Two rules that keep translation honest

1. **Keywords are words.** `cookie` and `cap_rate` are names; only a standalone
   `cook` is a keyword. The lexer decides this once, per token.
2. **String and comment contents are data.** They are never interpreted as code.

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
| `python wpp.py --tokens FILE.wpp` | Print the W++ token stream |
| `python wpp.py --ast FILE.wpp` | Print the W++ abstract syntax tree |
| `python wpp.py --version` | Print the W++ version |
| `python wpp.py --mute FILE.wpp` | Run without the error sound |
| `python wpp.py --sound FILE.wpp` | Force the error sound on, even when piped |

Exit codes: `0` success, `1` skill issue, `2` bad usage (missing file), `130` Ctrl-C.

## Learning W++

[`docs/WPP_Guide.pdf`](docs/WPP_Guide.pdf) is a complete guide for someone who
has never written W++ before: 57 pages covering every keyword, all the ordinary
Python that comes with it, the Skill Issue Protocol, the reserved-word rule, and
nine complete programs to read..

Every example in it was executed by the interpreter while the PDF was being
written, and the printed output is what actually came back. Rebuild it with:

```bash
python docs/build_guide.py
```

That needs `reportlab` (`pip install reportlab`) - the only dependency in the
project, and only for regenerating the PDF. Running W++ itself still needs
nothing but Python. `tests/test_guide.py` re-runs every example in the guide as
part of the normal test suite, so the language cannot change without the guide
being checked against it.

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

A program that prints without stopping is capped at 1 MB of output, and its
output is coalesced into chunks rather than sent line by line, so a runaway
`grind` loop cannot lock the page up.

The editor is Monaco when it can be reached, and a small built-in editor
otherwise, so the playground still works offline.

`python playground/server.py --port 9000 --no-browser` changes the port and
skips opening a browser.

> The playground executes the code it is given. It binds to `127.0.0.1` so it is
> reachable only from your machine - do not expose it to a network.

## Deploying the playground

The playground runs W++ two ways from the same files, and picks one at load
time by asking whether a backend is there:

| | Where W++ runs | Used when |
| --- | --- | --- |
| **Server engine** | `playground/server.py`, one child process per program | you run it locally |
| **Browser engine** | the same `wpplang` package under Pyodide, in a Web Worker | there is no backend |

The frontend cannot tell them apart: both emit the same records, so the editor,
the inline input caret, the Skill Issue Protocol and the runaway-loop limit
behave identically.

### Static hosting (Vercel, Netlify, GitHub Pages)

The site is **static files with no build step**, because the compiler's Python
sources are committed as `playground/static/wpp-sources.json`. Point the host at
`playground/static` and that is the whole deployment. `vercel.json` already does
this:

```json
{ "outputDirectory": "playground/static" }
```

So linking the repository to Vercel deploys a working playground. Nothing runs
on the server — the compiler is downloaded and executed in the visitor's
browser, which is also why this is safe to expose: there is no backend to
execute code on.

Regenerate the bundle after changing the compiler:

```bash
python tools/build_web_bundle.py
```

`tests/test_web_bundle.py` fails if the committed bundle no longer matches the
package, so it cannot quietly go stale.

### What the browser engine costs

- **A first-load download** of Pyodide (CPython on WebAssembly, tens of MB from
  a CDN) and a few seconds to start. After that a program runs in milliseconds.
- **Interactive `dm()` works by replay.** A browser cannot pause synchronous
  Python to wait for typing without extra isolation headers, so instead the
  program is run again from the start with each new answer, and the transcript
  is rebuilt. For the small programs W++ is for this is invisible - each attempt
  takes milliseconds - but a program whose output depends on `random` or the
  clock can differ between attempts.
- **A runaway loop is stopped by discarding the worker**, which is the only way
  to interrupt synchronous Python in a browser. The next run boots a fresh one
  in the background.

### Do not host the server engine publicly

`playground/server.py` executes the code it is given, with a timeout and no
sandbox. It binds `127.0.0.1` deliberately. The browser engine is the one to
deploy: the visitor's own browser runs their own code, and there is nothing of
yours for it to reach.

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
| `ZeroDivisionError` | 🚨 Math ain't mathing: Bro tried to divide by zero (ZeroDivisionError) |
| `IndentationError` | 🚨 Your spaces are looking a little sus (IndentationError) |
| `KeyboardInterrupt` | 🚨 Go touch grass, you've been looping forever (KeyboardInterrupt) |

### The error sound

A failing program plays `audio/fah.mp3`.

In the **playground** it plays whenever an error appears; the speaker button in
the output panel mutes and unmutes it, and the browser remembers your choice.

On the **command line** it plays only when stderr is a terminal, so piping
output into a file or another tool stays silent - and so does the test suite.
`--mute` turns it off, `--sound` forces it on, and `WPP_MUTE=1` in the
environment mutes it everywhere. Command-line flags beat the environment
variable.

Everything about the sound is best effort: if the file is missing, or the
machine has no way to play an MP3, the sound is skipped and the error is
reported exactly as before. Replace `audio/fah.mp3` to change it.

Any exception outside this table is reported as
`🚨 Unspecified skill issue (ExceptionName)` with the same file/line context — you
never get a raw Python traceback.

## Tests

```bash
python -m unittest discover -s tests -t .
```

Covers every keyword translation, word-boundary and string-literal safety,
expressions, functions, conditionals, loops, collections, I/O, exit codes, every
Skill Issue message, and the official spec examples run end to end.

`tests/test_programs.py` holds whole programs with exact expected output -
ternaries, comprehensions, loop-else, generators, classes, decorators,
f-strings, quicksort, a sieve, BFS, matrix multiplication - plus the diagnostics
for errors raised inside comprehensions, generators, methods and decorated
functions. `tests/test_playground.py` covers the API: interactive prompts,
several in a row, prompts inside a loop, the compute budget, Stop,
runaway-output handling, and child-process cleanup.

`tests/test_compiler.py` tests each compiler stage on its own - lexer, parser
and AST shape, semantic rules, code generation, source mapping.
`tests/test_compiler_equivalence.py` checks the compiler against the
pre-v1.2 regex translator (kept at `tests/reference_translator.py`, and on no
execution path): both target Python, so for every program in the repository the
two must generate Python that parses to the same tree. That is how this
refactor was shown to change no behaviour.

## Project layout

```
wpp.py                     CLI entry point
wpplang/keywords.py        the Official Dictionary (single source of truth)
wpplang/compiler/lexer.py  W++ source -> W++ tokens
wpplang/compiler/parser.py W++ tokens -> W++ AST
wpplang/compiler/nodes.py  the W++ AST node types
wpplang/compiler/semantic.py  whole-tree W++ rules
wpplang/compiler/codegen.py   W++ AST -> Python, plus the line map
wpplang/translator.py      the stable translate() front door
wpplang/runner.py          compile + execute, exit codes
wpplang/errors.py          the Skill Issue Protocol
playground/server.py    local web playground (stdlib HTTP server)
playground/_worker.py   one child process per playground run
playground/static/      the playground front end, including the favicon
playground/static/engine.js      picks the server or the browser engine
playground/static/wpp-worker.js  runs the compiler under Pyodide
playground/static/wpp-sources.json  the compiler, bundled for the browser
playground/make_favicon.py  redraws static/favicon.ico from the same mark
tools/build_web_bundle.py   rebuilds wpp-sources.json
docs/WPP_Guide.pdf      the complete learning guide
docs/build_guide.py     builds the guide, running every example in it
examples/               runnable W++ programs
tests/                  automated test suite
```

To add a keyword, add one line to `wpplang/keywords.py`. Everything else follows.

## Current limitations

- **W++ keywords are reserved words**, everywhere. You cannot name a function,
  class, method, parameter or keyword argument after one, for the same reason
  Python will not let you write `def break()`: `cook dip(self)` would become
  `def break(self)`, and a call written `dip()` would become `break()` anyway.
  Definitions get a clear error saying which word is the problem:

  ```
  $ python wpp.py stack.wpp
  🚨 Negative Aura: Bro forgot how to type (SyntaxError)
     where: stack.wpp, line 2
        2 | cook dip(self):
     details: 'dip' is a W++ keyword (it becomes Python's 'break'), so it cannot be used as a name
  ```

  Names that merely *contain* a keyword (`cookie`, `cap_rate`, `bet_size`) are
  fine, and so are attributes: `self.cap = 10` and `stack.dip()` both work,
  because a name after a dot is never a keyword.
- **Python keywords are not aliased.** `and`, `or`, `not`, `in`, `is`, `import`,
  `class`, `try`/`except`, `lambda` and friends are written the Python way; the spec
  only defines the 19 words above.
- **The translator is not a full Python parser.** It is a literal-aware regex pass.
  It understands strings (single, double, triple, raw, byte, f-strings) and comments,
  which covers real programs, but it does not build a syntax tree.
- **Errors are reported one at a time** — the first failure stops the program, as in
  Python.
- **No REPL** and no `.wpp` module imports: a program is a single file.
- **The compiler needs whole statements.** The old translator would rewrite any
  fragment of text; the parser wants a program. `cook squad(x):` with no body is
  no longer accepted, which is a deliberate change - it was never valid W++.
- **A keyword is rejected wherever a name is required**, including as a
  parameter or a keyword-argument name. The old translator let `f(bet=1)`
  through as `f(if=1)`, which Python then refused with a confusing message about
  code you never wrote; it is now refused up front, naming the word and the
  line. Also a deliberate change.
- **The playground is a local development tool**, not a hosted sandbox. It runs
  programs as your user account with only a time limit, so it belongs on your
  own machine and nowhere else.

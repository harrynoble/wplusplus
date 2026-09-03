/* The browser execution engine: the real W++ compiler, running under Pyodide.
 *
 * This is what makes the playground deployable as static files. There is no
 * server: the same `wpplang` package that runs from the command line is loaded
 * into CPython-on-WebAssembly and asked to compile and run the program.
 *
 * It lives in a Worker for two reasons. A runaway `grind` loop can be stopped
 * by terminating the worker, which is the only way to interrupt synchronous
 * Python in a browser; and the page stays responsive while a program runs.
 *
 * Interactive input works by replay. Python's `input()` is synchronous and a
 * worker cannot pause for the user without SharedArrayBuffer and the
 * cross-origin isolation headers that come with it, so instead: the program
 * runs with the answers given so far, and when `dm()` asks for one that is not
 * there yet the run stops and the main thread is told what the prompt was.
 * When the user types, the program is run again from the start with the longer
 * list of answers. The transcript is reset on each attempt, so what the user
 * sees is an ordinary session - each attempt is milliseconds.
 */

const PYODIDE_VERSION = "0.26.4";
const PYODIDE_BASE = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";

let pyodide = null;
let driver = null;

// The Python side of the engine. Kept here rather than in the bundle because it
// belongs to the browser build, not to the language.
const DRIVER = `
import io, sys

sys.path.insert(0, "/wpp")


def _make_driver():
    from wpplang import run_source

    def run(source, answers, emit):
        """Run one attempt. Returns a dict describing how it ended."""
        supply = iter(list(answers))
        needed = {}

        class Stream(io.TextIOBase):
            """Sends program output straight out to the page."""

            def writable(self):
                return True

            def isatty(self):
                return False

            def write(self, text):
                if not isinstance(text, str):
                    text = str(text)
                if text:
                    emit(text)
                return len(text)

            def flush(self):
                pass

        out = Stream()

        def wpp_input(prompt=""):
            text = "" if prompt is None else str(prompt)
            if text:
                out.write(text)
            try:
                value = next(supply)
            except StopIteration:
                # No answer for this prompt yet. Remember what was asked and
                # unwind: SystemExit is a BaseException, so an ordinary
                # \`except Exception\` in the program will not swallow it, and
                # run_source treats it as a clean exit rather than an error.
                needed["prompt"] = text
                raise SystemExit(0)
            out.write(value + "\\n")
            return value

        saved = (sys.stdout, sys.stderr)
        sys.stdout = out
        sys.stderr = out
        try:
            result = run_source(source, "main.wpp",
                                extra_globals={"input": wpp_input})
        finally:
            sys.stdout, sys.stderr = saved

        if "prompt" in needed:
            return {"kind": "input", "prompt": needed["prompt"]}
        return {
            "kind": "result",
            "exitCode": result.exit_code,
            "error": result.error_details,
        }

    return run


_driver = _make_driver()
`;

async function boot(sources) {
  self.importScripts(PYODIDE_BASE + "pyodide.js");
  pyodide = await self.loadPyodide({ indexURL: PYODIDE_BASE });

  // Write the compiler into the virtual filesystem and import it from there,
  // exactly as it would be imported from a checkout.
  pyodide.FS.mkdirTree("/wpp/wpplang/compiler");
  for (const [path, text] of Object.entries(sources.modules)) {
    pyodide.FS.writeFile("/wpp/" + path, text, { encoding: "utf8" });
  }

  await pyodide.runPythonAsync(DRIVER);
  driver = pyodide.globals.get("_driver");
}

/* One attempt at running the program. */
function attempt(source, answers) {
  post({ event: "reset" });

  const emit = (text) => post({ event: "stdout", text: text });
  let outcome;
  try {
    outcome = driver(source, answers, emit).toJs({ dict_converter: Object.fromEntries });
  } catch (error) {
    // A failure here is the engine's, not the program's.
    post({
      event: "result",
      exitCode: 1,
      error: {
        message: "The W++ engine could not run that",
        exception: "EngineError",
        path: null, line: null, source_line: null,
        detail: String((error && error.message) || error),
      },
    });
    return;
  }

  if (outcome.kind === "input") {
    post({ event: "input", prompt: outcome.prompt });
    return;
  }
  post({
    event: "result",
    exitCode: outcome.exitCode,
    error: normaliseError(outcome.error),
  });
}

/* Pyodide hands back a Map for a Python dict; the page wants a plain object. */
function normaliseError(error) {
  if (!error) return null;
  if (error instanceof Map) return Object.fromEntries(error);
  return error;
}

function post(message) {
  self.postMessage(message);
}

self.onmessage = async (event) => {
  const message = event.data;

  if (message.type === "boot") {
    try {
      await boot(message.sources);
      post({ event: "ready" });
    } catch (error) {
      post({ event: "bootFailed", detail: String((error && error.message) || error) });
    }
    return;
  }

  if (message.type === "run") {
    if (!driver) {
      post({ event: "bootFailed", detail: "the engine is not ready yet" });
      return;
    }
    attempt(message.source, message.answers || []);
  }
};

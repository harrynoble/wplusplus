"""W++ Playground - a local web front end for the W++ interpreter.

Run it with:

    python playground/server.py

Then open http://127.0.0.1:8000.

The server is deliberately small: it serves the static front end and exposes
three endpoints.  All language behaviour comes from the `wpplang` package, so
the playground and the CLI can never disagree about what W++ means.

    GET  /api/reference   the Official Dictionary and the Skill Issue table
    GET  /api/examples    the programs in examples/
    POST /api/run         {"source": "...", "stdin": "..."} -> run result

SECURITY: this executes the code it is given.  It binds to 127.0.0.1 so it is
reachable only from this machine.  Do not expose it to a network.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wpplang import CATEGORIES, KEYWORDS, SKILL_ISSUES, __version__  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATIC_DIR = os.path.join(HERE, "static")
WORKER = os.path.join(HERE, "_worker.py")
EXAMPLES_DIR = os.path.join(ROOT, "examples")

# Limits that keep a runaway program from taking the playground down with it.
RUN_TIMEOUT_SECONDS = 10
MAX_SOURCE_BYTES = 200_000
MAX_STDIN_BYTES = 20_000

# Which examples appear in the Examples menu, in order.  `stdin` pre-fills the
# input box so an example that calls dm() still runs in one click.
EXAMPLES = [
    {"id": "hello", "name": "Hello World", "file": "hello.wpp", "stdin": ""},
    {"id": "vibe_check", "name": "Vibe Check", "file": "vibe_check.wpp", "stdin": "Claude"},
    {"id": "fizzbuzz", "name": "FizzBuzz", "file": "fizzbuzz.wpp", "stdin": ""},
    {"id": "collections", "name": "Collections", "file": "collections.wpp", "stdin": ""},
    {"id": "keyword_tour", "name": "Keyword Tour", "file": "keyword_tour.wpp", "stdin": "Claude"},
    {"id": "oops", "name": "Skill Issue", "file": "oops.wpp", "stdin": ""},
]


class RequestError(Exception):
    """A bad request, carrying the status code to answer with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class PlaygroundHandler(SimpleHTTPRequestHandler):
    """Serves the front end, plus the three JSON endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/reference":
            return self._send_json(
                {
                    "version": __version__,
                    "keywords": KEYWORDS,
                    "categories": CATEGORIES,
                    "skillIssues": SKILL_ISSUES,
                }
            )
        if self.path.split("?")[0] == "/api/examples":
            return self._send_json(load_examples())
        if self.path.startswith("/api/"):
            return self._send_json({"error": "unknown endpoint"}, status=404)
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/run":
            return self._send_json({"error": "unknown endpoint"}, status=404)

        try:
            payload = self._read_json()
        except RequestError as exc:
            return self._send_json({"error": str(exc)}, status=exc.status)

        source = payload.get("source", "")
        stdin_text = payload.get("stdin", "")
        if not isinstance(source, str) or not isinstance(stdin_text, str):
            return self._send_json({"error": "source and stdin must be strings"}, status=400)
        if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
            return self._send_json({"error": "program is too large"}, status=413)
        if len(stdin_text.encode("utf-8")) > MAX_STDIN_BYTES:
            return self._send_json({"error": "input is too large"}, status=413)

        return self._send_json(execute(source, stdin_text))

    def _read_json(self):
        """Read the request body, then decide whether we like it.

        The body is always consumed - even when it is too big - because
        replying before the client has finished sending resets the connection
        instead of delivering the error.
        """
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise RequestError("request body is required")

        hard_cap = MAX_SOURCE_BYTES + MAX_STDIN_BYTES + 1024
        body = self.rfile.read(min(length, hard_cap))

        remaining = length - len(body)
        while remaining > 0:  # drain the overflow so the socket stays usable
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)

        if length > hard_cap:
            raise RequestError("program is too large", status=413)

        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RequestError("request body must be JSON")

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # The front end is served from this origin only; nothing is cached so
        # that editing static/ and reloading is enough to see the change.
        if self.path.endswith((".js", ".css", ".html")) or self.path == "/":
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        # One tidy line per request instead of the default noise.
        sys.stderr.write("  {} {}\n".format(self.command, self.path))


def load_examples():
    """Read the example programs off disk so examples/ stays the only copy."""
    loaded = []
    for entry in EXAMPLES:
        path = os.path.join(EXAMPLES_DIR, entry["file"])
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            loaded.append(
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "stdin": entry["stdin"],
                    "source": handle.read(),
                }
            )
    return loaded


def execute(source, stdin_text, timeout=RUN_TIMEOUT_SECONDS):
    """Run W++ source in a child process and return a JSON-ready result."""
    started = time.monotonic()

    with tempfile.TemporaryDirectory(prefix="wpp-run-") as workdir:
        source_path = os.path.join(workdir, "main.wpp")
        result_path = os.path.join(workdir, "result.json")
        with open(source_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(source)

        environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")

        try:
            completed = subprocess.run(
                [sys.executable, WORKER, source_path, result_path],
                input=stdin_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=workdir,
                env=environment,
            )
        except subprocess.TimeoutExpired as expired:
            # A program that never finishes is exactly the skill issue the spec
            # already has a message for, so reuse it rather than inventing one.
            return {
                "stdout": _decode(expired.stdout),
                "stderr": "",
                "exitCode": 130,
                "timedOut": True,
                "durationMs": int((time.monotonic() - started) * 1000),
                "error": {
                    "message": SKILL_ISSUES["KeyboardInterrupt"],
                    "exception": "KeyboardInterrupt",
                    "path": "main.wpp",
                    "line": None,
                    "source_line": None,
                    "detail": "Stopped after {} seconds.".format(timeout),
                },
            }

        envelope = {"exitCode": completed.returncode, "error": None}
        if os.path.isfile(result_path):
            with open(result_path, "r", encoding="utf-8") as handle:
                envelope = json.load(handle)

        return {
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
            "exitCode": envelope.get("exitCode", 0),
            "timedOut": False,
            "durationMs": int((time.monotonic() - started) * 1000),
            "error": envelope.get("error"),
        }


def _decode(value):
    """Partial output from a timed-out child arrives as str or bytes."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve the W++ playground locally.")
    parser.add_argument("-p", "--port", type=int, default=8000)
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="interface to bind (default 127.0.0.1; only change this if you "
             "understand that the playground runs the code it is given)",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), PlaygroundHandler)
    url = "http://{}:{}".format(args.host, args.port)

    print("W++ playground {}".format(__version__))
    print("  {}".format(url))
    print("  This runs the W++ programs you give it. Keep it on this machine.")
    print("  Ctrl-C to stop.\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

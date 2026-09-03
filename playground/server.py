"""W++ Playground - a local web front end for the W++ interpreter.

Run it with:

    python playground/server.py

Then open http://127.0.0.1:8000.

A run is a *session*, not a single request, because a W++ program can stop and
ask for input half way through:

    POST /api/run      {"source": "..."}          -> {"sessionId": "..."}
    GET  /api/stream   ?session=ID                -> server-sent events
    POST /api/input    {"session": ID, "text": ""} -> feeds one line to dm()
    POST /api/stop     {"session": ID}            -> ends the run

    GET  /api/reference  the Official Dictionary and the Skill Issue table
    GET  /api/examples   the programs in examples/

All language behaviour comes from the `wpplang` package, so the playground and
the CLI can never disagree about what W++ means.

SECURITY: this executes the code it is given.  It binds to 127.0.0.1 so it is
reachable only from this machine.  Do not expose it to a network.
"""

import argparse
import json
import os
import queue
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import shutil
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wpplang import CATEGORIES, KEYWORDS, SKILL_ISSUES, __version__  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATIC_DIR = os.path.join(HERE, "static")
WORKER = os.path.join(HERE, "_worker.py")
EXAMPLES_DIR = os.path.join(ROOT, "examples")

# Limits that keep one program from taking the playground down with it.
COMPUTE_TIMEOUT_SECONDS = 10     # time actually spent running, not waiting
INPUT_IDLE_SECONDS = 600         # how long a program may sit waiting for input
MAX_SOURCE_BYTES = 200_000
MAX_INPUT_BYTES = 10_000
MAX_OUTPUT_BYTES = 1_000_000
MAX_LIVE_SESSIONS = 8
SESSION_RETENTION_SECONDS = 120  # keep a finished session around to be drained

# Which examples appear in the Examples menu, in order.
EXAMPLES = [
    {"id": "hello", "name": "Hello World", "file": "hello.wpp"},
    {"id": "vibe_check", "name": "Vibe Check", "file": "vibe_check.wpp"},
    {"id": "fizzbuzz", "name": "FizzBuzz", "file": "fizzbuzz.wpp"},
    {"id": "collections", "name": "Collections", "file": "collections.wpp"},
    {"id": "keyword_tour", "name": "Keyword Tour", "file": "keyword_tour.wpp"},
    {"id": "oops", "name": "Skill Issue", "file": "oops.wpp"},
]


class RequestError(Exception):
    """A bad request, carrying the status code to answer with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------- session


class Session:
    """One running W++ program, plus the event stream describing it."""

    def __init__(self, source, timeout=COMPUTE_TIMEOUT_SECONDS):
        self.id = secrets.token_hex(8)
        self.source = source
        self.timeout = timeout

        self.events = queue.Queue()
        self.process = None
        self.workdir = None

        self._lock = threading.RLock()
        self.finished = threading.Event()
        self.finished_at = None

        # Waiting for input must not count against the compute budget, so the
        # budget is accumulated in slices between prompts.
        self.waiting = False
        self.waiting_since = None
        self.compute_used = 0.0
        self.resumed_at = None

        self.started_at = None
        self.output_bytes = 0
        self._result_sent = False
        self._pending = None  # outcome claimed by a stop or a timeout

    # -- lifecycle

    def start(self):
        self.workdir = tempfile.mkdtemp(prefix="wpp-run-")
        source_path = os.path.join(self.workdir, "main.wpp")
        with open(source_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(self.source)

        environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.started_at = time.monotonic()
        self.resumed_at = self.started_at

        self.process = subprocess.Popen(
            [sys.executable, WORKER, source_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=self.workdir,
            env=environment,
        )

        threading.Thread(target=self._read_channel, daemon=True).start()
        threading.Thread(target=self._watchdog, daemon=True).start()

    def _read_channel(self):
        """Forward the worker's ordered record stream to our event queue."""
        try:
            for line in self.process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue  # not ours; ignore rather than derail the run
                self._handle(record)
        except (OSError, ValueError):
            pass

        # The worker's stdout closed, so the program is over one way or another.
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._terminate()
        self._finish(None)

    def _handle(self, record):
        event = record.get("event")

        if event in ("stdout", "stderr"):
            text = record.get("text") or ""
            with self._lock:
                self.output_bytes += len(text.encode("utf-8", "replace"))
                over_limit = self.output_bytes > MAX_OUTPUT_BYTES
            self._emit(record)
            if over_limit:
                self._stop_with(
                    exit_code=1,
                    error={
                        "message": "Output limit reached",
                        "exception": "OutputLimit",
                        "path": None,
                        "line": None,
                        "source_line": None,
                        "detail": "This program printed more than {} KB.".format(
                            MAX_OUTPUT_BYTES // 1000
                        ),
                    },
                )
            return

        if event == "input":
            with self._lock:
                # Bank the compute time spent so far and stop the clock.
                if self.resumed_at is not None:
                    self.compute_used += time.monotonic() - self.resumed_at
                    self.resumed_at = None
                self.waiting = True
                self.waiting_since = time.monotonic()
            self._emit(record)
            return

        if event == "result":
            self._finish(record)
            return

        self._emit(record)

    def _watchdog(self):
        """Enforce the compute budget, and evict programs waiting forever."""
        while not self.finished.wait(0.2):
            now = time.monotonic()
            with self._lock:
                if self.waiting:
                    idle = now - (self.waiting_since or now)
                    expired = idle > INPUT_IDLE_SECONDS
                    reason = "idle"
                else:
                    used = self.compute_used + (now - (self.resumed_at or now))
                    expired = used > self.timeout
                    reason = "timeout"

            if expired:
                if reason == "timeout":
                    # A program that never finishes is exactly the skill issue
                    # the spec already has a message for, so reuse it.
                    self._stop_with(
                        exit_code=130,
                        timed_out=True,
                        error={
                            "message": SKILL_ISSUES["KeyboardInterrupt"],
                            "exception": "KeyboardInterrupt",
                            "path": "main.wpp",
                            "line": None,
                            "source_line": None,
                            "detail": "Stopped after {} seconds of running.".format(self.timeout),
                        },
                    )
                else:
                    self._stop_with(
                        exit_code=130,
                        error={
                            "message": "Stopped while waiting for input",
                            "exception": "InputTimeout",
                            "path": None,
                            "line": None,
                            "source_line": None,
                            "detail": "Nothing was entered for {} minutes.".format(
                                INPUT_IDLE_SECONDS // 60
                            ),
                        },
                    )
                return

    # -- input and stopping

    def send_input(self, text):
        """Feed one line to the program's stdin."""
        with self._lock:
            if self.finished.is_set() or self.process is None:
                raise RequestError("this run has already finished", status=409)
            if self.process.poll() is not None:
                raise RequestError("this run has already finished", status=409)
            # The clock restarts now that the program can make progress again.
            self.waiting = False
            self.waiting_since = None
            self.resumed_at = time.monotonic()
            stream = self.process.stdin

        try:
            stream.write(text + "\n")
            stream.flush()
        except (OSError, ValueError):
            raise RequestError("this run is no longer accepting input", status=409)

    def stop(self):
        self._stop_with(exit_code=130, stopped=True)

    def _stop_with(self, exit_code, error=None, timed_out=False, stopped=False):
        record = {
            "event": "result",
            "exitCode": exit_code,
            "error": error,
            "timedOut": timed_out,
            "stopped": stopped,
        }
        # Claim the outcome *before* killing the process.  Terminating unblocks
        # the reader thread, which would otherwise race us to _finish() and
        # report a plain exit instead of "timed out" or "stopped".
        with self._lock:
            if not self._result_sent:
                self._pending = record

        self._terminate()
        self._finish(record)

    def _terminate(self):
        process = self.process
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        except OSError:
            pass

    def _finish(self, record):
        """Emit the final result exactly once and close the stream."""
        with self._lock:
            if self._result_sent:
                return
            self._result_sent = True
            if record is None:
                # A stop or a timeout may already have decided the outcome.
                record = self._pending

        if record is None:
            # The worker exited without a result: synthesise a plain one.
            code = self.process.returncode if self.process else 1
            record = {"event": "result", "exitCode": code or 0, "error": None}

        record.setdefault("timedOut", False)
        record.setdefault("stopped", False)
        # Report time spent *running*, not time spent waiting for someone to
        # type: a program the user answered after a minute still ran for 12 ms.
        record["durationMs"] = int(self._compute_time() * 1000)

        self._emit(record)
        self.events.put(None)  # sentinel: the stream is over
        self.finished_at = time.monotonic()
        self.finished.set()

        # stdin is closed so a program blocked on dm() unblocks and exits.
        if self.process is not None and self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except (OSError, ValueError):
                pass

        self._schedule_cleanup()

    def _schedule_cleanup(self):
        """Delete the run directory once the child has really exited.

        Waiting matters on Windows, where a directory that is still some
        process's working directory cannot be removed.
        """
        process, workdir = self.process, self.workdir
        self.workdir = None
        if workdir is None:
            return

        def clean():
            if process is not None:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            shutil.rmtree(workdir, ignore_errors=True)

        threading.Thread(target=clean, daemon=True).start()

    def _compute_time(self):
        """Seconds the program has actually spent running."""
        with self._lock:
            elapsed = self.compute_used
            if self.resumed_at is not None:
                elapsed += time.monotonic() - self.resumed_at
            return elapsed

    def _emit(self, record):
        self.events.put(record)

    def cleanup(self):
        self._terminate()
        if self.workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)
            self.workdir = None


class SessionStore:
    """Keeps the live sessions and reaps the ones nobody needs any more."""

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()
        threading.Thread(target=self._reap_forever, daemon=True).start()

    def create(self, source, timeout=COMPUTE_TIMEOUT_SECONDS):
        session = Session(source, timeout=timeout)
        with self._lock:
            live = [s for s in self._sessions.values() if not s.finished.is_set()]
            # Keep a lid on how many programs can run at once.
            for old in sorted(live, key=lambda s: s.started_at or 0)[:max(0, len(live) - MAX_LIVE_SESSIONS + 1)]:
                old.stop()
            self._sessions[session.id] = session
        session.start()
        return session

    def get(self, session_id):
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise RequestError("unknown session", status=404)
        return session

    def _reap_forever(self):
        while True:
            time.sleep(5)
            now = time.monotonic()
            with self._lock:
                stale = [
                    key for key, session in self._sessions.items()
                    if session.finished_at is not None
                    and now - session.finished_at > SESSION_RETENTION_SECONDS
                ]
                gone = [self._sessions.pop(key) for key in stale]
            for session in gone:
                session.cleanup()

    def shutdown(self):
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.cleanup()


SESSIONS = SessionStore()


# --------------------------------------------------------------------- handler


class PlaygroundHandler(SimpleHTTPRequestHandler):
    """Serves the front end, plus the JSON and event-stream endpoints."""

    # Streaming needs 1.1 semantics; every other response sets Content-Length.
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/reference":
            return self._send_json({
                "version": __version__,
                "keywords": KEYWORDS,
                "categories": CATEGORIES,
                "skillIssues": SKILL_ISSUES,
            })
        if path == "/api/examples":
            return self._send_json(load_examples())
        if path == "/api/stream":
            return self._stream()
        if path.startswith("/api/"):
            return self._send_json({"error": "unknown endpoint"}, status=404)
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/run":
                return self._run()
            if path == "/api/input":
                return self._input()
            if path == "/api/stop":
                return self._stop()
            return self._send_json({"error": "unknown endpoint"}, status=404)
        except RequestError as exc:
            return self._send_json({"error": str(exc)}, status=exc.status)

    # -- endpoints

    def _run(self):
        payload = self._read_json()
        source = payload.get("source", "")
        if not isinstance(source, str):
            raise RequestError("source must be a string")
        if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise RequestError("program is too large", status=413)

        timeout = COMPUTE_TIMEOUT_SECONDS
        requested = payload.get("timeout")
        if isinstance(requested, (int, float)) and 0 < requested <= COMPUTE_TIMEOUT_SECONDS:
            timeout = requested  # tests use a shorter budget

        session = SESSIONS.create(source, timeout=timeout)
        return self._send_json({"sessionId": session.id})

    def _input(self):
        payload = self._read_json()
        text = payload.get("text", "")
        if not isinstance(text, str):
            raise RequestError("text must be a string")
        if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
            raise RequestError("input line is too long", status=413)
        # A single line is a single line: strip anything that would smuggle more.
        text = text.replace("\r", "").replace("\n", "")

        SESSIONS.get(self._session_id(payload)).send_input(text)
        return self._send_json({"ok": True})

    def _stop(self):
        payload = self._read_json()
        SESSIONS.get(self._session_id(payload)).stop()
        return self._send_json({"ok": True})

    def _stream(self):
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        session_id = ""
        for part in query.split("&"):
            key, _, value = part.partition("=")
            if key == "session":
                session_id = value

        try:
            session = SESSIONS.get(session_id)
        except RequestError as exc:
            return self._send_json({"error": str(exc)}, status=exc.status)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        try:
            while True:
                try:
                    record = session.events.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")  # hold the connection
                    self.wfile.flush()
                    continue

                if record is None:
                    break
                self.wfile.write(
                    ("data: " + json.dumps(record) + "\n\n").encode("utf-8")
                )
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            # The page went away (reload, closed tab): the run goes with it.
            session.stop()

    # -- plumbing

    def _session_id(self, payload):
        session_id = payload.get("session", "")
        if not isinstance(session_id, str) or not session_id:
            raise RequestError("session is required")
        return session_id

    def _read_json(self):
        """Read the request body, then decide whether we like it.

        The body is always consumed - even when it is too big - because
        replying before the client has finished sending resets the connection
        instead of delivering the error.
        """
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise RequestError("request body is required")

        hard_cap = MAX_SOURCE_BYTES + MAX_INPUT_BYTES + 1024
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
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RequestError("request body must be JSON")
        if not isinstance(payload, dict):
            raise RequestError("request body must be a JSON object")
        return payload

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # Nothing is cached, so editing static/ and reloading is enough.
        if self.path.endswith((".js", ".css", ".html")) or self.path == "/":
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        # One tidy line per request instead of the default noise.
        sys.stderr.write("  {} {}\n".format(self.command, self.path))


def sweep_old_run_dirs(max_age_seconds=3600):
    """Clear run directories left behind by a server that was killed."""
    root = tempfile.gettempdir()
    now = time.time()
    try:
        names = os.listdir(root)
    except OSError:
        return
    for name in names:
        if not name.startswith("wpp-run-"):
            continue
        path = os.path.join(root, name)
        try:
            if now - os.path.getmtime(path) > max_age_seconds:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def load_examples():
    """Read the example programs off disk so examples/ stays the only copy."""
    loaded = []
    for entry in EXAMPLES:
        path = os.path.join(EXAMPLES_DIR, entry["file"])
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            loaded.append({
                "id": entry["id"],
                "name": entry["name"],
                "source": handle.read(),
            })
    return loaded


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

    sweep_old_run_dirs()

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
        SESSIONS.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Subprocess entry point for one playground run.

The playground never executes user code inside the web server.  Each run is a
fresh child process, which gives us a hard timeout for runaway loops, isolation
from the server's own state, and a stdin we can feed one line at a time.

Everything the parent needs travels on this process's stdout as one ordered
stream of JSON records, one per line:

    {"event": "stdout", "text": "..."}     program output
    {"event": "stderr", "text": "..."}     program output written to stderr
    {"event": "input",  "prompt": "..."}   blocked on dm(), waiting for a line
    {"event": "result", "exitCode": 0, "error": null}

Using a single channel for output *and* control is the point: if the prompt
travelled on stdout while the "now waiting" signal travelled on stderr, the
parent could observe them out of order and draw the input caret above the text
that asked for it.  One ordered stream makes that impossible.
"""

import io
import json
import os
import sys
import threading

# The repository root, so `wpplang` imports without installation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wpplang import run_source  # noqa: E402  (path setup must come first)


class Channel:
    """The ordered JSON-lines stream back to the parent."""

    def __init__(self, stream):
        self._stream = stream
        # User code may start threads that print, so serialise the writes.
        self._lock = threading.Lock()

    def send(self, record):
        line = json.dumps(record)
        with self._lock:
            self._stream.write(line + "\n")
            self._stream.flush()


class ProxyStream(io.TextIOBase):
    """Stands in for sys.stdout / sys.stderr and forwards writes as records.

    Writes are gathered until a newline shows up, which keeps one `yap` call
    from turning into half a dozen records, and are flushed explicitly before
    an input prompt so the caret always lands after the prompt text.
    """

    def __init__(self, channel, event):
        self._channel = channel
        self._event = event
        self._parts = []

    def writable(self):
        return True

    def isatty(self):
        return False

    def write(self, text):
        if not isinstance(text, str):
            text = str(text)
        if text:
            self._parts.append(text)
            if "\n" in text:
                self.flush()
        return len(text)

    def flush(self):
        if not self._parts:
            return
        text = "".join(self._parts)
        del self._parts[:]
        self._channel.send({"event": self._event, "text": text})


def make_input(channel, out, stdin):
    """Build the interactive `input` that W++'s `dm` resolves to."""

    def wpp_input(prompt=""):
        text = "" if prompt is None else str(prompt)
        if text:
            out.write(text)
        out.flush()  # the prompt must be on screen before we announce the wait
        channel.send({"event": "input", "prompt": text})

        line = stdin.readline()
        if not line:
            # Only reachable if the parent closed stdin, i.e. the run is over.
            raise EOFError("EOF when reading a line")
        return line.rstrip("\r\n")

    return wpp_input


def main():
    source_path = sys.argv[1]

    # Take a private handle on the real stdout before redirecting it, so the
    # channel keeps working once sys.stdout belongs to the program.
    channel = Channel(os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1, newline="\n"))
    out = ProxyStream(channel, "stdout")
    err = ProxyStream(channel, "stderr")
    stdin = sys.stdin

    sys.stdout = out
    sys.stderr = err

    try:
        with open(source_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        # `main.wpp` keeps the reported path short and stable in the UI.
        result = run_source(
            source,
            "main.wpp",
            extra_globals={"input": make_input(channel, out, stdin)},
        )
        out.flush()
        err.flush()
        channel.send({"event": "result", "exitCode": result.exit_code, "error": result.error_details})
    except BaseException as exc:  # noqa: BLE001 - the worker itself failed
        out.flush()
        err.flush()
        channel.send({
            "event": "result",
            "exitCode": 1,
            "error": {
                "message": "The playground could not run that program",
                "exception": type(exc).__name__,
                "path": None,
                "line": None,
                "source_line": None,
                "detail": str(exc),
            },
        })

    # Always exit 0: the result record carries the program's real exit code, so
    # a non-zero status here would only mean the worker itself failed.
    return 0


if __name__ == "__main__":
    sys.exit(main())

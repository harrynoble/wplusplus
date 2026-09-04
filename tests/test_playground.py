"""Playground tests: the session API, interactive input, and the guards."""

import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from playground import server as playground


class QuietHandler(playground.PlaygroundHandler):
    """The real handler, minus the request logging."""

    def log_message(self, fmt, *args):
        pass


class ApiTestCase(unittest.TestCase):
    """Runs the real server on an ephemeral port for the duration of the class."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.base = "http://127.0.0.1:{}".format(cls.server.server_address[1])
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    # -- plumbing

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def post(self, path, payload):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def drive(self, source, answers=(), timeout=None, pause=0.0):
        """Run a program the way the browser does.

        Starts a session, reads its event stream, and types *answers* into the
        prompts as they arrive.  Returns (output, result_record, events).
        """
        body = {"source": source}
        if timeout is not None:
            body["timeout"] = timeout
        session_id = self.post("/api/run", body)["sessionId"]

        stream = urllib.request.urlopen(
            self.base + "/api/stream?session=" + session_id, timeout=60
        )
        pending = list(answers)
        output, events = [], []

        for raw in stream:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            record = json.loads(line[len("data: "):])
            events.append(record)

            if record["event"] in ("stdout", "stderr"):
                output.append(record["text"])
            elif record["event"] == "input":
                if pause:
                    time.sleep(pause)
                self.post("/api/input", {
                    "session": session_id,
                    "text": pending.pop(0) if pending else "",
                })
            elif record["event"] == "result":
                return "".join(output), record, events

        return "".join(output), None, events


class StaticTests(ApiTestCase):
    def test_index_is_served(self):
        with urllib.request.urlopen(self.base + "/", timeout=30) as response:
            body = response.read().decode("utf-8")
        self.assertIn("W++ Playground", body)
        self.assertIn("app.js", body)

    def test_no_emoji_in_the_front_end(self):
        # The UI must stay emoji-free; the siren belongs to the CLI only.
        for name in ("/", "/app.js", "/app.css"):
            with urllib.request.urlopen(self.base + name, timeout=30) as response:
                body = response.read().decode("utf-8")
            with self.subTest(file=name):
                self.assertNotIn("\U0001f6a8", body)

    def test_the_error_sound_is_served(self):
        import os
        from wpplang.sound import ERROR_SOUND

        with urllib.request.urlopen(self.base + "/audio/fah.mp3", timeout=30) as response:
            body = response.read()
            self.assertEqual(response.headers["Content-Type"], "audio/mpeg")
        self.assertEqual(len(body), os.path.getsize(ERROR_SOUND))
        self.assertTrue(body[:3] == b"ID3" or body[0] == 0xFF)

    def test_the_favicon_is_served_in_both_formats(self):
        with urllib.request.urlopen(self.base + "/favicon.svg", timeout=30) as response:
            svg = response.read().decode("utf-8")
            self.assertEqual(response.headers["Content-Type"], "image/svg+xml")
        self.assertIn("<svg", svg)
        self.assertIn("#3b82f6", svg)  # the accent, so the tab matches the app

        with urllib.request.urlopen(self.base + "/favicon.ico", timeout=30) as response:
            ico = response.read()
            self.assertIn(response.headers["Content-Type"],
                          ("image/x-icon", "image/vnd.microsoft.icon"))
        # An ICO starts: reserved 0, type 1, then the number of images.
        self.assertEqual(ico[:4], b"\x00\x00\x01\x00")
        self.assertGreaterEqual(int.from_bytes(ico[4:6], "little"), 3)

    def test_the_favicon_really_holds_every_size(self):
        # Pillow's ICO writer silently drops sizes larger than its source
        # image, so the container is built by hand - this proves it worked.
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        import io
        with urllib.request.urlopen(self.base + "/favicon.ico", timeout=30) as response:
            data = response.read()
        sizes = sorted(Image.open(io.BytesIO(data)).info["sizes"])
        self.assertIn((16, 16), sizes)
        self.assertIn((32, 32), sizes)
        for size in sizes:
            frame = Image.open(io.BytesIO(data))
            frame.size = size
            frame.load()
            self.assertEqual(frame.size, size)

    def test_the_two_favicon_formats_draw_the_same_mark(self):
        # favicon.svg is hand-written and favicon.ico is generated, so the two
        # can drift. The numbers behind them must stay identical.
        import os
        import re

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "playground", "static", "favicon.svg"),
                  encoding="utf-8") as handle:
            svg = handle.read()
        with open(os.path.join(root, "playground", "make_favicon.py"),
                  encoding="utf-8") as handle:
            generator = handle.read()

        def numbers(text):
            return [float(value) for value in re.findall(r"[\d.]+", text)]

        svg_points = numbers(re.search(r'd="M([^"]+)"', svg).group(1))
        gen_points = numbers(re.search(r"POINTS = \[(.+)\]", generator).group(1))
        self.assertEqual(svg_points, gen_points, "the W outline differs")

        self.assertEqual(
            float(re.search(r'stroke-width="([\d.]+)"', svg).group(1)),
            float(re.search(r"STROKE = ([\d.]+)", generator).group(1)),
            "the stroke weight differs")
        self.assertEqual(
            float(re.search(r'rx="([\d.]+)"', svg).group(1)),
            float(re.search(r"CORNER = ([\d.]+)", generator).group(1)),
            "the corner radius differs")

        red, green, blue = re.search(
            r"ACCENT = \((\d+), (\d+), (\d+)", generator).groups()
        self.assertEqual(
            re.search(r'fill="(#[0-9a-fA-F]{6})"', svg).group(1).lower(),
            "#%02x%02x%02x" % (int(red), int(green), int(blue)),
            "the tile colour differs")

    def test_the_page_links_the_favicon(self):
        with urllib.request.urlopen(self.base + "/", timeout=30) as response:
            page = response.read().decode("utf-8")
        self.assertIn('href="favicon.svg"', page)
        self.assertIn('href="favicon.ico"', page)

    def test_the_page_has_a_sound_toggle(self):
        with urllib.request.urlopen(self.base + "/", timeout=30) as response:
            page = response.read().decode("utf-8")
        self.assertIn('id="sound-button"', page)
        self.assertIn('aria-pressed', page)

        with urllib.request.urlopen(self.base + "/app.js", timeout=30) as response:
            script = response.read().decode("utf-8")
        # The sound plays on an error, and the choice is remembered. The path
        # is relative so the page works from a subpath as well as the root.
        self.assertIn("playErrorSound", script)
        self.assertIn("audio/fah.mp3", script)
        self.assertIn("localStorage", script)

    def test_no_stdin_box_remains(self):
        # Input happens inline in the output panel now.
        with urllib.request.urlopen(self.base + "/", timeout=30) as response:
            body = response.read().decode("utf-8")
        self.assertNotIn("stdin-input", body)


class ReferenceTests(ApiTestCase):
    def test_reference_exposes_the_dictionary(self):
        data = self.get("/api/reference")
        self.assertEqual(data["keywords"]["bodycount"], "len")
        self.assertEqual(data["categories"]["cook"], "Function declaration")

    def test_reference_exposes_the_skill_issues(self):
        data = self.get("/api/reference")
        self.assertEqual(
            data["skillIssues"]["NameError"],
            "Bro is making up words now (NameError)",
        )

    def test_examples_are_loaded_from_disk(self):
        examples = self.get("/api/examples")
        names = [item["name"] for item in examples]
        for required in ("Hello World", "Vibe Check", "FizzBuzz"):
            self.assertIn(required, names)

    def test_examples_carry_their_source(self):
        examples = {item["id"]: item for item in self.get("/api/examples")}
        self.assertIn("check_vibe", examples["vibe_check"]["source"])


class RunTests(ApiTestCase):
    def test_hello_world(self):
        output, result, _ = self.drive('yap("Hello world")')
        self.assertEqual(output.strip(), "Hello world")
        self.assertIsNone(result["error"])
        self.assertEqual(result["exitCode"], 0)

    def test_fizzbuzz(self):
        source = (
            "cook fizzbuzz(limit):\n"
            "    spam i in range(1, limit + 1):\n"
            "        bet i % 15 == 0:\n"
            "            yap('FizzBuzz')\n"
            "        plotwist i % 3 == 0:\n"
            "            yap('Fizz')\n"
            "        nah:\n"
            "            yap(i)\n"
            "\n"
            "fizzbuzz(5)"
        )
        output, _, _ = self.drive(source)
        self.assertEqual(output.split(), ["1", "2", "Fizz", "4", "5"])

    def test_error_is_structured_and_has_no_emoji(self):
        output, result, _ = self.drive("yap(1)\nyap(nope)")
        error = result["error"]
        self.assertEqual(error["message"], "Bro is making up words now (NameError)")
        self.assertEqual(error["exception"], "NameError")
        self.assertEqual(error["line"], 2)
        self.assertEqual(error["source_line"], "yap(nope)")
        self.assertNotIn("\U0001f6a8", json.dumps(result))
        self.assertEqual(output.strip(), "1")  # output before the failure survives

    def test_syntax_error_reports_a_line(self):
        _, result, _ = self.drive("cook f(:")
        self.assertEqual(
            result["error"]["message"],
            "Negative Aura: Bro forgot how to type (SyntaxError)",
        )
        self.assertEqual(result["error"]["line"], 1)

    def test_each_run_is_isolated(self):
        self.drive("leftover = 1")
        _, result, _ = self.drive("yap(leftover)")
        self.assertEqual(result["error"]["exception"], "NameError")

    def test_stderr_is_reported_separately(self):
        _, _, events = self.drive("import sys\nsys.stderr.write('to stderr')")
        kinds = {event["event"] for event in events}
        self.assertIn("stderr", kinds)


class InteractiveInputTests(ApiTestCase):
    """dm() must block for a real answer, not hit EOF."""

    def test_single_prompt(self):
        output, result, _ = self.drive(
            'name = dm("Who are you? ")\nyap("hi", name)', ["Claude"]
        )
        self.assertEqual(output, "Who are you? hi Claude\n")
        self.assertIsNone(result["error"])

    def test_prompt_arrives_before_the_input_request(self):
        # The caret must never be drawn above the text that asked for it.
        _, _, events = self.drive('yap("first")\nx = dm("then: ")\nyap(x)', ["ok"])
        kinds = [event["event"] for event in events]
        self.assertLess(kinds.index("stdout"), kinds.index("input"))
        prompts = [e["text"] for e in events if e["event"] == "stdout"]
        self.assertIn("then: ", prompts)

    def test_several_prompts_in_a_row(self):
        output, result, _ = self.drive(
            'a = dm("first: ")\nb = dm("second: ")\nc = dm("third: ")\nyap(a, b, c)',
            ["one", "two", "three"],
        )
        self.assertEqual(output, "first: second: third: one two three\n")
        self.assertIsNone(result["error"])

    def test_prompt_inside_a_loop(self):
        source = (
            "total = 0\n"
            "spam i in range(3):\n"
            '    total = total + int(dm("n: "))\n'
            'yap("total", total)'
        )
        output, result, _ = self.drive(source, ["1", "2", "3"])
        self.assertIn("total 6", output)
        self.assertIsNone(result["error"])

    def test_empty_answer_is_accepted(self):
        output, result, _ = self.drive('x = dm("name: ")\nyap(bodycount(x))', [""])
        self.assertIn("0", output)
        self.assertIsNone(result["error"])

    def test_official_vibe_check_runs_interactively(self):
        import os
        path = os.path.join(playground.EXAMPLES_DIR, "vibe_check.wpp")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        output, result, _ = self.drive(source, ["Claude"])
        self.assertIn("Vibe check:  W AI", output)
        self.assertIsNone(result["error"])

    def test_waiting_for_input_does_not_burn_the_compute_budget(self):
        # A one-second budget must survive a much longer pause at the prompt.
        output, result, _ = self.drive(
            'x = dm("slow: ")\nyap("got", x)', ["late"], timeout=1, pause=2.5
        )
        self.assertFalse(result["timedOut"])
        self.assertIsNone(result["error"])
        self.assertIn("got late", output)

    def test_reported_duration_excludes_the_wait(self):
        _, result, _ = self.drive(
            'x = dm("q: ")\nyap(x)', ["a"], timeout=5, pause=1.5
        )
        self.assertLess(result["durationMs"], 1500)

    def test_input_after_the_run_is_refused(self):
        session_id = self.post("/api/run", {"source": 'yap("done")'})["sessionId"]
        # Drain the stream so the session is definitely finished.
        stream = urllib.request.urlopen(
            self.base + "/api/stream?session=" + session_id, timeout=30
        )
        for raw in stream:
            if b'"result"' in raw:
                break
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/input", {"session": session_id, "text": "late"})
        self.assertEqual(caught.exception.code, 409)

    def test_a_newline_cannot_be_smuggled_into_one_line(self):
        # Two prompts, but the first answer tries to satisfy both at once.
        output, result, _ = self.drive(
            'a = dm("a: ")\nb = dm("b: ")\nyap("[" + a + "][" + b + "]")',
            ["one\ntwo", "second"],
        )
        self.assertIn("[onetwo][second]", output)
        self.assertIsNone(result["error"])


class RunawayOutputTests(ApiTestCase):
    """A loop that prints must stay watchable, and one that prints without a
    newline must not look like a program producing nothing at all."""

    def test_output_without_a_newline_still_arrives(self):
        # The worker buffers writes; without a periodic flush a program that
        # never prints a newline showed no output whatsoever, and the buffer
        # died with the process when the timeout killed it.
        output, _, _ = self.drive(
            "import sys\n"
            "sys.stdout.write('partial line')\n"
            "grind nocap:\n"
            "    x = 1",
            timeout=1,
        )
        self.assertIn("partial line", output)

    def test_a_flooding_loop_is_delivered_in_few_events(self):
        # One record per printed line meant ~200k browser events per megabyte,
        # which froze the tab. Output is coalesced into chunks instead.
        output, _, events = self.drive(
            'grind nocap:\n    yap("spam")', timeout=1
        )
        chunks = [event for event in events if event["event"] == "stdout"]
        self.assertGreater(len(output), 100_000, "expected the loop to flood")
        self.assertLess(len(chunks), 400, "too many events for the output size")

    def test_a_flooding_loop_still_respects_the_budget(self):
        started = time.monotonic()
        _, result, _ = self.drive('grind nocap:\n    yap("spam")', timeout=1)
        elapsed = time.monotonic() - started
        self.assertIsNotNone(result)
        # Delivering the backlog used to take many times the budget.
        self.assertLess(elapsed, 10, "took %.1fs for a 1s budget" % elapsed)

    def test_output_limit_ends_a_flood(self):
        _, result, _ = self.drive(
            "import sys\ngrind nocap:\n    sys.stdout.write('x')", timeout=8
        )
        # Either guard may win the race; both must end the run cleanly.
        self.assertIn(
            result["error"]["message"],
            (
                "Output limit reached",
                "Go touch grass, you've been looping forever (KeyboardInterrupt)",
            ),
        )

    def test_the_playground_still_works_after_a_flood(self):
        # "Nothing works after that, you have to reload."
        self.drive('grind nocap:\n    yap("spam")', timeout=1)
        output, result, _ = self.drive('yap("still alive")')
        self.assertEqual(output.strip(), "still alive")
        self.assertIsNone(result["error"])

    def test_interactive_input_still_works_after_a_flood(self):
        self.drive('grind nocap:\n    yap("spam")', timeout=1)
        output, result, _ = self.drive(
            'name = dm("who? ")\nyap("hi", name)', ["Claude"]
        )
        self.assertEqual(output, "who? hi Claude\n")
        self.assertIsNone(result["error"])


class GuardTests(ApiTestCase):
    def test_runaway_loop_is_stopped(self):
        started = time.monotonic()
        _, result, _ = self.drive("grind nocap:\n    x = 1", timeout=1)
        self.assertTrue(result["timedOut"])
        self.assertEqual(
            result["error"]["message"],
            "Go touch grass, you've been looping forever (KeyboardInterrupt)",
        )
        self.assertEqual(result["exitCode"], 130)
        self.assertLess(time.monotonic() - started, 20)

    def test_partial_output_survives_a_timeout(self):
        output, _, _ = self.drive(
            "yap('before the loop')\ngrind nocap:\n    x = 1", timeout=1
        )
        self.assertIn("before the loop", output)

    def test_stop_ends_a_waiting_program(self):
        session_id = self.post(
            "/api/run", {"source": 'x = dm("never: ")\nyap(x)'}
        )["sessionId"]
        stream = urllib.request.urlopen(
            self.base + "/api/stream?session=" + session_id, timeout=30
        )
        result = None
        for raw in stream:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            record = json.loads(line[len("data: "):])
            if record["event"] == "input":
                self.post("/api/stop", {"session": session_id})
            elif record["event"] == "result":
                result = record
                break
        self.assertIsNotNone(result)
        self.assertTrue(result["stopped"])

    def test_no_worker_survives_a_stop(self):
        session = playground.SESSIONS.create('x = dm("wait: ")')
        # Let the child reach the prompt before pulling the plug.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not session.waiting:
            time.sleep(0.05)
        session.stop()
        session.process.wait(timeout=10)
        self.assertIsNotNone(session.process.poll())

    def test_oversized_program_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/run", {"source": "x = 1\n" * 60000})
        self.assertEqual(caught.exception.code, 413)

    def test_unknown_endpoint(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/api/nope")
        self.assertEqual(caught.exception.code, 404)

    def test_unknown_session(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/input", {"session": "nope", "text": "x"})
        self.assertEqual(caught.exception.code, 404)

    def test_non_json_body_is_rejected(self):
        request = urllib.request.Request(
            self.base + "/api/run",
            data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=30)
        self.assertEqual(caught.exception.code, 400)

    def test_wrong_types_are_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/run", {"source": 42})
        self.assertEqual(caught.exception.code, 400)

    def test_run_directory_is_cleaned_up(self):
        import os
        session = playground.SESSIONS.create('yap("bye")')
        workdir = session.workdir
        self.assertTrue(os.path.isdir(workdir))
        session.finished.wait(timeout=20)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and os.path.isdir(workdir):
            time.sleep(0.1)
        self.assertFalse(os.path.isdir(workdir))


if __name__ == "__main__":
    unittest.main()

"""Playground tests: the JSON API and the sandboxing around it."""

import json
import threading
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

    def test_vibe_check_ships_with_input(self):
        examples = {item["id"]: item for item in self.get("/api/examples")}
        self.assertEqual(examples["vibe_check"]["stdin"], "Claude")
        self.assertIn("check_vibe", examples["vibe_check"]["source"])


class RunTests(ApiTestCase):
    def test_hello_world(self):
        result = self.post("/api/run", {"source": 'yap("Hello world")'})
        self.assertEqual(result["stdout"].strip(), "Hello world")
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
        result = self.post("/api/run", {"source": source})
        self.assertEqual(result["stdout"].split(), ["1", "2", "Fizz", "4", "5"])

    def test_stdin_feeds_dm(self):
        result = self.post(
            "/api/run",
            {"source": 'name = dm("Who? ")\nyap(name)', "stdin": "Claude\n"},
        )
        self.assertIn("Claude", result["stdout"])
        self.assertIsNone(result["error"])

    def test_error_is_structured_and_has_no_emoji(self):
        result = self.post("/api/run", {"source": "yap(1)\nyap(nope)"})
        error = result["error"]
        self.assertEqual(error["message"], "Bro is making up words now (NameError)")
        self.assertEqual(error["exception"], "NameError")
        self.assertEqual(error["line"], 2)
        self.assertEqual(error["source_line"], "yap(nope)")
        self.assertNotIn("\U0001f6a8", json.dumps(result))
        # Output produced before the failure is still returned.
        self.assertEqual(result["stdout"].strip(), "1")

    def test_syntax_error_reports_a_line(self):
        result = self.post("/api/run", {"source": "cook f(:"})
        self.assertEqual(
            result["error"]["message"],
            "Negative Aura: Bro forgot how to type (SyntaxError)",
        )
        self.assertEqual(result["error"]["line"], 1)

    def test_each_run_is_isolated(self):
        self.post("/api/run", {"source": "leftover = 1"})
        result = self.post("/api/run", {"source": "yap(leftover)"})
        self.assertEqual(result["error"]["exception"], "NameError")

    def test_run_reports_duration(self):
        result = self.post("/api/run", {"source": "yap(1)"})
        self.assertIsInstance(result["durationMs"], int)
        self.assertFalse(result["timedOut"])


class GuardTests(ApiTestCase):
    def test_runaway_loop_is_stopped(self):
        # Called directly so the test can use a one-second budget.
        result = playground.execute("grind nocap:\n    x = 1", "", timeout=1)
        self.assertTrue(result["timedOut"])
        self.assertEqual(
            result["error"]["message"],
            "Go touch grass, you've been looping forever (KeyboardInterrupt)",
        )
        self.assertEqual(result["exitCode"], 130)

    def test_partial_output_survives_a_timeout(self):
        result = playground.execute(
            "yap('before the loop')\ngrind nocap:\n    x = 1", "", timeout=2
        )
        self.assertIn("before the loop", result["stdout"])

    def test_oversized_program_is_rejected(self):
        payload = {"source": "x = 1\n" * 60000}
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/run", payload)
        self.assertEqual(caught.exception.code, 413)

    def test_unknown_endpoint(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/api/nope")
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


if __name__ == "__main__":
    unittest.main()

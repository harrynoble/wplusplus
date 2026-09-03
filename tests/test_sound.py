"""Tests for the optional error sound.

Nothing here plays audio: the point is that the decision to play, and the
refusal to ever crash over it, are both correct.  Whether the clip is audible
is something only a person can check.
"""

import os
import subprocess
import sys
import unittest
from unittest import mock

import wpp as cli
from wpplang import sound

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Args:
    """Stand-in for the parsed command line."""

    def __init__(self, mute=False, sound=False):
        self.mute = mute
        self.sound = sound


class SoundFileTests(unittest.TestCase):
    def test_the_error_sound_ships_with_the_project(self):
        self.assertTrue(sound.available(), sound.ERROR_SOUND)
        self.assertEqual(
            os.path.normcase(sound.ERROR_SOUND),
            os.path.normcase(os.path.join(ROOT, "audio", "fah.mp3")))

    def test_it_really_is_an_mp3(self):
        with open(sound.ERROR_SOUND, "rb") as handle:
            head = handle.read(4)
        # Either an ID3 tag or a bare MPEG frame header.
        self.assertTrue(
            head[:3] == b"ID3" or (head[0] == 0xFF and head[1] & 0xE0 == 0xE0),
            "audio/fah.mp3 does not look like an mp3: %r" % head)

    def test_a_missing_file_is_not_an_error(self):
        self.assertFalse(sound.available("no-such-file.mp3"))
        self.assertFalse(sound.play("no-such-file.mp3"))
        self.assertFalse(sound.play_error_sound("no-such-file.mp3", muted=False))

    def test_a_broken_player_is_swallowed(self):
        # Whatever goes wrong down there, W++ must still report the error.
        with mock.patch.object(sound, "_play_windows", side_effect=OSError("nope")), \
             mock.patch.object(sound, "_play_linux", side_effect=OSError("nope")), \
             mock.patch.object(sound, "_play_command", side_effect=OSError("nope")):
            self.assertFalse(sound.play(sound.ERROR_SOUND))


class MuteTests(unittest.TestCase):
    def test_muted_never_reaches_the_player(self):
        with mock.patch.object(sound, "play") as player:
            self.assertFalse(sound.play_error_sound(muted=True))
        player.assert_not_called()

    def test_unmuted_reaches_the_player(self):
        with mock.patch.object(sound, "play", return_value=True) as player:
            self.assertTrue(sound.play_error_sound(muted=False))
        player.assert_called_once()

    def test_the_environment_can_mute(self):
        for value in ("1", "true", "YES", "on"):
            with mock.patch.dict(os.environ, {"WPP_MUTE": value}):
                self.assertTrue(sound.is_muted(), value)
        for value in ("0", "false", "no", ""):
            with mock.patch.dict(os.environ, {"WPP_MUTE": value}):
                self.assertFalse(sound.is_muted(), value)

    def test_no_environment_variable_means_unmuted(self):
        environment = dict(os.environ)
        environment.pop("WPP_MUTE", None)
        with mock.patch.dict(os.environ, environment, clear=True):
            self.assertFalse(sound.is_muted())


class CliDecisionTests(unittest.TestCase):
    """--mute beats --sound beats WPP_MUTE beats whether stderr is a terminal."""

    def decide(self, args, tty, env=None):
        environment = dict(os.environ)
        environment.pop("WPP_MUTE", None)
        environment.update(env or {})
        stream = mock.Mock()
        stream.isatty.return_value = tty
        with mock.patch.dict(os.environ, environment, clear=True), \
             mock.patch.object(cli.sys, "stderr", stream):
            return cli.wants_sound(args)

    def test_a_terminal_plays_by_default(self):
        self.assertTrue(self.decide(Args(), tty=True))

    def test_piped_output_stays_silent(self):
        self.assertFalse(self.decide(Args(), tty=False))

    def test_mute_wins_over_everything(self):
        self.assertFalse(self.decide(Args(mute=True), tty=True))
        self.assertFalse(self.decide(Args(mute=True, sound=True), tty=True))

    def test_sound_forces_it_when_piped(self):
        self.assertTrue(self.decide(Args(sound=True), tty=False))

    def test_the_environment_mutes_a_terminal(self):
        self.assertFalse(self.decide(Args(), tty=True, env={"WPP_MUTE": "1"}))

    def test_an_explicit_flag_beats_the_environment(self):
        self.assertTrue(
            self.decide(Args(sound=True), tty=False, env={"WPP_MUTE": "1"}))

    def test_a_stream_without_isatty_is_silent(self):
        broken = object()  # no isatty at all
        environment = dict(os.environ)
        environment.pop("WPP_MUTE", None)
        with mock.patch.dict(os.environ, environment, clear=True), \
             mock.patch.object(cli.sys, "stderr", broken):
            self.assertFalse(cli.wants_sound(Args()))


class CliBehaviourTests(unittest.TestCase):
    """The error report must not depend on the sound in any way."""

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "wpp.py"), *args],
            capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
            env=dict(os.environ, WPP_MUTE="1"), timeout=60,
        )

    def test_a_muted_failure_is_reported_normally(self):
        path = os.path.join(ROOT, "tests", "_sound_probe.wpp")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("yap(1 / 0)\n")
        try:
            done = self.run_cli("--mute", path)
            self.assertEqual(done.returncode, 1)
            self.assertIn("Math ain't mathing", done.stderr)
        finally:
            os.remove(path)

    def test_the_flags_are_documented(self):
        done = self.run_cli("--help")
        self.assertIn("--mute", done.stdout)
        self.assertIn("--sound", done.stdout)

    def test_a_working_program_is_unaffected(self):
        done = self.run_cli(os.path.join(ROOT, "examples", "hello.wpp"))
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout.strip(), "Hello world")


if __name__ == "__main__":
    unittest.main()

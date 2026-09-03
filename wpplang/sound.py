"""Optional error sound.

When a program fails, W++ can play `audio/fah.mp3`.  Everything here is best
effort: if the file is missing, or the machine has no way to play it, the sound
is skipped and the error is still reported exactly as before.  Nothing in this
module is allowed to raise.

Muting:

* the command line takes ``--mute`` (never play) and ``--sound`` (always play)
* ``WPP_MUTE=1`` in the environment mutes it everywhere
* the playground has its own toggle, remembered by the browser
"""

import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERROR_SOUND = os.path.join(ROOT, "audio", "fah.mp3")

# Never hold the process open longer than this waiting for a sound to finish.
MAX_WAIT_SECONDS = 6.0

_TRUTHY = {"1", "true", "yes", "on"}


def available(path=ERROR_SOUND):
    """Is there a sound file to play?"""
    return os.path.isfile(path)


def is_muted():
    """True when the environment asks for silence."""
    return os.environ.get("WPP_MUTE", "").strip().lower() in _TRUTHY


def play_error_sound(path=ERROR_SOUND, muted=None):
    """Play the error sound unless muted.  Returns whether it played."""
    if muted is None:
        muted = is_muted()
    if muted:
        return False
    return play(path)


def play(path=ERROR_SOUND):
    """Play an audio file, returning whether it actually started."""
    if not os.path.isfile(path):
        return False
    try:
        if sys.platform.startswith("win"):
            return _play_windows(path)
        if sys.platform == "darwin":
            return _play_command(["afplay", path])
        return _play_linux(path)
    except Exception:  # noqa: BLE001 - a silent failure is the right one here
        return False


def _play_windows(path):
    """Play through MCI, which is part of Windows and handles MP3.

    The process is usually about to exit, so we wait for the clip to finish -
    otherwise it would be cut off the moment W++ returns.  The wait is bounded
    by the clip's own length and by MAX_WAIT_SECONDS.
    """
    import ctypes

    send = ctypes.WinDLL("winmm").mciSendStringW
    send.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
                     ctypes.c_void_p]
    send.restype = ctypes.c_uint

    alias = "wpp_error_sound"
    answer = ctypes.create_unicode_buffer(128)

    if send('open "%s" type mpegvideo alias %s' % (path, alias), None, 0, None):
        return False
    try:
        seconds = 2.0
        if not send("status %s length" % alias, answer, 128, None):
            if answer.value.strip().isdigit():
                seconds = int(answer.value.strip()) / 1000.0
        if send("play %s" % alias, None, 0, None):
            return False
        time.sleep(min(max(seconds, 0.1), MAX_WAIT_SECONDS))
        return True
    finally:
        send("close %s" % alias, None, 0, None)


def _play_linux(path):
    """Try the players a desktop Linux box is likely to have."""
    for player, args in (
        ("paplay", [path]),
        ("mpg123", ["-q", path]),
        ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet", path]),
        ("aplay", [path]),
    ):
        if shutil.which(player):
            return _play_command([player] + args)
    return False


def _play_command(command):
    """Run an external player, bounded so it can never hang W++."""
    if not shutil.which(command[0]):
        return False
    try:
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=MAX_WAIT_SECONDS,
            check=False,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False

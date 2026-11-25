"""Helpers that keep the plugin's unit tests runnable on Windows (Git Bash, Python as `py -3`) as
well as on Linux and macOS. Stdlib only. The test files import it; the plugin's scripts and hooks
never do. On POSIX every helper behaves as the plain call it replaces."""
import functools
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time

WINDOWS = os.name == "nt"


@functools.lru_cache(maxsize=None)
def hook_python():
    """The Python a hook wrapper names in its messages: the first of python3, python, `py -3`
    that runs under sh, as the wrappers try them (on Windows `python3` and `python` can be
    Microsoft Store stubs that exit 9009). "python3" when none runs or there is no sh."""
    probe = 'for c in python3 python "py -3"; do $c -c "" >/dev/null 2>&1 && ' \
            '{ printf %s "$c"; exit 0; }; done; exit 1'
    try:
        p = subprocess.run(["sh", "-c", probe], capture_output=True, stdin=subprocess.DEVNULL)
    except OSError:
        return "python3"
    return p.stdout.decode() if p.returncode == 0 and p.stdout else "python3"


def symlink(test, source, link, **kw):
    """os.symlink; on Windows, where creating one needs a privilege or Developer Mode
    (WinError 1314), the test is skipped instead."""
    try:
        os.symlink(source, link, **kw)
    except (OSError, NotImplementedError) as exc:
        if not WINDOWS:
            raise
        test.skipTest("symlinks not permitted here: %s" % exc)


def _clear_read_only_and_retry(func, path, _exc):
    """rmtree's error handler: a read-only file (git keeps its objects read-only, which Windows
    refuses to delete, WinError 5) is made writable and removed again; a file another process
    still holds (WinError 32) gets a few short retries. On Windows a temporary folder that still
    cannot go is left behind; elsewhere the error is raised."""
    for attempt in range(5):
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        except OSError:
            pass
        try:
            func(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if not WINDOWS:
                raise
            time.sleep(0.1 * (attempt + 1))
    # Windows only: give up on this entry; the rest of the folder is still removed.


def rmtree(path, ignore_errors=False):
    """shutil.rmtree that also removes read-only files (git objects on Windows)."""
    if ignore_errors:
        shutil.rmtree(path, ignore_errors=True)
    elif sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_read_only_and_retry)
    else:
        shutil.rmtree(path, onerror=_clear_read_only_and_retry)


def temp_dir():
    """tempfile.TemporaryDirectory; on Windows (Python 3.10+) a file still held by another
    process at cleanup is left behind instead of failing the test (WinError 32)."""
    if WINDOWS and sys.version_info >= (3, 10):
        return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    return tempfile.TemporaryDirectory()


def bash():
    """The bash to run a scaffold script with, or None. On Windows: Git Bash (beside the `sh` or
    under the Git install on PATH), never System32's bash.exe, which starts WSL instead."""
    if not WINDOWS:
        return shutil.which("bash")
    candidates = []
    for tool, rel in (("sh", ("bash.exe",)), ("git", ("..", "bin", "bash.exe")),
                      ("git", ("..", "usr", "bin", "bash.exe"))):
        found = shutil.which(tool)
        if found:
            candidates.append(os.path.join(os.path.dirname(found), *rel))
    candidates.append(shutil.which("bash"))
    system = os.path.normcase(os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), ""))
    for path in candidates:
        if path and os.path.isfile(path) and \
                not os.path.normcase(os.path.abspath(path)).startswith(system):
            return os.path.normpath(path)
    return None


def path_too_long(path):
    """True on Windows when `path` is at or over MAX_PATH (260), which most tools there refuse
    unless long paths are turned on."""
    return WINDOWS and len(os.path.abspath(path)) >= 260

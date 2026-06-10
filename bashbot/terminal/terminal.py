import asyncio
import os
import signal
import sys
import threading
import time
from inspect import isawaitable

import pyte
from enum import Enum

from bashbot.core.settings import settings
from bashbot.core.utils import execute_async, get_logger
from bashbot.terminal.control import TerminalControl
from bashbot.terminal.shortcuts import replace_shortcuts

TERMINATE_WAIT_SECONDS = 0.5


class TerminalState(Enum):
    CLOSED = 0
    OPEN = 1
    FROZEN = 2
    BROKEN = 3


class TerminalStartupError(Exception):
    pass


class Terminal:
    def __init__(self, name: str,
                 sh_path: str, su_path: str = None,
                 login: str = None, password: str = None,
                 on_change=None, on_exit=None):
        self.session_id = None
        self.name = name
        self.sh_path = sh_path
        self.su_path = su_path
        self.login = login
        self.password = password
        self.on_change = on_change
        self.on_exit = on_exit

        self.controls = {}
        self.interactive = settings().get('terminal.interactive_by_default')
        self.auto_submit = settings().get('terminal.submit_by_default')

        self.state: TerminalState = TerminalState.CLOSED
        cols = settings().get('terminal.cols', 120)
        rows = settings().get('terminal.rows', 40)
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)

        self.fd = None
        self.pid = None
        self.content = None

        self.refresh_timer = None
        self.event_loop = None
        self._closing = False
        self._exited = False
        self._pty_generation = 0
        self._repost_requested = False

    def open(self, loop=None):
        self.__validate_startup()
        self.event_loop = loop or asyncio.get_running_loop()
        self.__reset_screen()
        self._closing = False
        self._exited = False
        self._pty_generation += 1
        self.pid, self.fd = os.forkpty()

        if self.pid == 0:
            env = os.environ.copy()
            env['TERM'] = settings().get('terminal.term', 'xterm-256color')
            if self.login:
                os.execve(self.su_path, [self.su_path, "-", self.login, "-s", self.sh_path], env)
            else:
                os.execve(self.sh_path, [self.sh_path], env)
            sys.exit(0)
        else:
            self.state = TerminalState.OPEN
            pty_watcher = threading.Thread(target=self.__monitor_pty, args=(self.fd, self._pty_generation), daemon=True)
            pty_watcher.start()

    def restart(self, loop=None):
        self.close(notify=False)
        self.open(loop=loop)

    def __validate_startup(self):
        if not hasattr(os, 'forkpty'):
            raise TerminalStartupError(
                'Interactive terminal sessions require a Unix-like host with forkpty support. '
                'Run BashBot inside Linux, WSL, or Docker.'
            )

        if not os.path.exists(self.sh_path):
            raise TerminalStartupError(f'Shell path does not exist: {self.sh_path}')

        if self.login and not os.path.exists(self.su_path):
            raise TerminalStartupError(f'su path does not exist: {self.su_path}')

    def close(self, force=False, notify=True):
        self._closing = True
        self.state = TerminalState.CLOSED

        self.__terminate_child(force=force)
        self.__close_fd()

        if self.refresh_timer:
            self.refresh_timer.cancel()
        if notify:
            self.__notify_change()

    def kill(self):
        self.close(force=True)

    def __reset_screen(self):
        cols = settings().get('terminal.cols', 120)
        rows = settings().get('terminal.rows', 40)
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        self.content = None

    def __close_fd(self):
        if self.fd is None:
            return

        try:
            os.close(self.fd)
        except OSError:
            pass
        finally:
            self.fd = None

    def __signal_child(self, sig):
        if not self.pid:
            return

        try:
            if hasattr(os, 'killpg'):
                os.killpg(self.pid, sig)
            else:
                os.kill(self.pid, sig)
        except OSError:
            try:
                os.kill(self.pid, sig)
            except OSError:
                pass

    def __terminate_child(self, force=False):
        if not self.pid:
            return

        kill_signal = getattr(signal, 'SIGKILL', signal.SIGTERM)
        if force:
            self.__signal_child(kill_signal)
            self.__wait_for_child(timeout=TERMINATE_WAIT_SECONDS)
            return

        close_signals = [
            getattr(signal, 'SIGHUP', signal.SIGTERM),
            signal.SIGTERM,
            kill_signal,
        ]
        for sig in close_signals:
            self.__signal_child(sig)
            if self.__wait_for_child(timeout=TERMINATE_WAIT_SECONDS):
                return

    def __wait_for_child(self, timeout=0):
        if not self.pid or not hasattr(os, 'waitpid'):
            return False

        deadline = time.monotonic() + timeout
        while True:
            try:
                waited_pid, _ = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                self.pid = None
                return True
            except OSError:
                return False

            if waited_pid:
                self.pid = None
                return True

            if timeout <= 0 or time.monotonic() >= deadline:
                return False

            time.sleep(0.05)

    def __finish(self, state, generation=None):
        if generation is not None and generation != self._pty_generation:
            return

        if self._exited:
            return

        self._exited = True
        if self.state != TerminalState.CLOSED:
            self.state = state

        self.__close_fd()
        self.__wait_for_child(timeout=1)

        if self.refresh_timer:
            self.refresh_timer.cancel()
        self.__notify_change()
        self.__notify_exit()


    def refresh(self):
        if self.refresh_timer and self.refresh_timer.is_alive():
            self.refresh_timer.cancel()

        interval = settings().get('terminal.max_refresh_frequency')
        self.refresh_timer = threading.Timer(interval, self.__notify_change)
        self.refresh_timer.start()

    def __notify_change(self):
        self.refresh_timer = None
        if self.event_loop and self.on_change:
            execute_async(self.event_loop, self.on_change(self, self.content))

    def __notify_exit(self):
        if not self.event_loop or not self.on_exit or self._closing:
            return

        result = self.on_exit(self, self.content)
        if isawaitable(result):
            execute_async(self.event_loop, result)

    def send_input(self, data: str):
        if self.state != TerminalState.OPEN:
            return

        data = replace_shortcuts(data)

        try:
            if self.fd is None:
                raise OSError()
            os.write(self.fd, data.encode("utf-8"))
        except OSError:
            if not self._closing:
                self.__finish(TerminalState.BROKEN)

    def add_control(self, emoji, content):
        self.controls[emoji] = TerminalControl(emoji, content)

    def remove_control(self, emoji):
        self.controls.pop(emoji, None)

    def search_control(self, phrase):
        return [label for label in self.controls.keys() if label.startswith(phrase)]

    def __monitor_pty(self, fd, generation):
        try:
            output = os.read(fd, 1024)
            if self.login:
                self.send_input(self.password + '\n')

            while output:
                if generation != self._pty_generation:
                    return

                self.stream.feed(output)
                self.content = '\n'.join(line.rstrip() for line in self.screen.display).rstrip('\n')

                if self.on_change and self.state == TerminalState.OPEN:
                    self.refresh()

                output = os.read(fd, 1024)
            if generation != self._pty_generation:
                return

            if not self._closing:
                self.__finish(TerminalState.CLOSED, generation=generation)
        except OSError:
            if generation != self._pty_generation:
                return

            if not self._closing:
                state = TerminalState.CLOSED if self.__wait_for_child() else TerminalState.BROKEN
                self.__finish(state, generation=generation)

import asyncio
import os
import sys
import threading
import pyte
from enum import Enum

from bashbot.core.settings import settings
from bashbot.core.utils import execute_async
from bashbot.terminal.control import TerminalControl
from bashbot.terminal.shortcuts import replace_shortcuts


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
                 on_change=None):
        self.name = name
        self.sh_path = sh_path
        self.su_path = su_path
        self.login = login
        self.password = password
        self.on_change = on_change

        self.controls = {}
        self.interactive = settings().get('terminal.interactive_by_default')
        self.auto_submit = settings().get('terminal.submit_by_default')

        self.state: TerminalState = TerminalState.CLOSED
        self.screen = pyte.Screen(80, 24)
        self.stream = pyte.ByteStream(self.screen)

        self.fd = None
        self.pid = None
        self.content = None

        self.refresh_timer = None
        self.event_loop = None

    def open(self, loop=None):
        self.__validate_startup()
        self.event_loop = loop or asyncio.get_running_loop()
        self.pid, self.fd = os.forkpty()

        if self.pid == 0:
            env = os.environ.copy()
            env['TERM'] = 'linux'
            if self.login:
                os.execve(self.su_path, [self.su_path, "-", self.login, "-s", self.sh_path], env)
            else:
                os.execve(self.sh_path, [self.sh_path], env)
            sys.exit(0)
        else:
            self.state = TerminalState.OPEN
            pty_watcher = threading.Thread(target=self.__monitor_pty, daemon=True)
            pty_watcher.start()

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

    def close(self):
        self.state = TerminalState.CLOSED
        self.refresh()
        try:
            os.close(self.fd)
        except OSError:
            pass

        if self.pid:
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                pass

    def refresh(self):
        if self.refresh_timer and self.refresh_timer.is_alive():
            return

        interval = settings().get('terminal.max_refresh_frequency')
        self.refresh_timer = threading.Timer(interval, self.__notify_change)
        self.refresh_timer.start()

    def __notify_change(self):
        if self.event_loop and self.on_change:
            execute_async(self.event_loop, self.on_change(self, self.content))

    def send_input(self, data: str):
        if self.state != TerminalState.OPEN:
            return

        data = replace_shortcuts(data)

        try:
            os.write(self.fd, data.encode("utf-8"))
        except OSError:
            self.state = TerminalState.BROKEN

    def add_control(self, emoji, content):
        self.controls[emoji] = TerminalControl(emoji, content)

    def remove_control(self, emoji):
        self.controls.pop(emoji, None)

    def search_control(self, phrase):
        return [label for label in self.controls.keys() if label.startswith(phrase)]

    def __monitor_pty(self):
        try:
            output = os.read(self.fd, 1024)
            if self.login:
                self.send_input(self.password + '\n')

            while output:
                self.stream.feed(output)
                self.content = '\n'.join(self.screen.display)

                if self.on_change and self.state == TerminalState.OPEN:
                    self.refresh()

                output = os.read(self.fd, 1024)
        except OSError:
            self.state = TerminalState.BROKEN
            return

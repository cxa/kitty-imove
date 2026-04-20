#!/usr/bin/env python
"""Kitten: interactive move-window overlay (like resize mode)."""

import os
import socket
import subprocess
import sys

from kitty.key_encoding import EventType, KeyEvent
from kitty.utils import ScreenSize

from kittens.tui.handler import Handler
from kittens.tui.loop import Loop
from kittens.tui.operations import styled


def _kitten_exe() -> str:
    from kitty.constants import kitten_exe
    return kitten_exe()


def _safe_pipe() -> tuple[int, int]:
    r, w = os.pipe()
    os.set_inheritable(r, False)
    os.set_inheritable(w, False)
    return r, w


class MoveWindow(Handler):

    print_on_fail: str | None = None

    def initialize(self) -> None:
        self.rc_fd = -1
        self.password = ''
        listen_on = os.environ.get('KITTY_LISTEN_ON', '')
        if listen_on.startswith('fd:'):
            self.rc_fd = int(listen_on.partition(':')[-1])
            os.set_inheritable(self.rc_fd, False)
            # Read password from the socket
            with socket.fromfd(self.rc_fd, socket.AF_UNIX, socket.SOCK_STREAM) as s:
                data = s.recv(256)
            if data.endswith(b'\n'):
                self.password = data.strip().decode()
        self.cmd.set_cursor_visible(False)
        self.cmd.set_line_wrapping(False)
        self.draw_screen()

    def do_move(self, direction: str) -> None:
        if self.rc_fd < 0:
            return
        prefix = [_kitten_exe(), '@']
        r = -1
        pass_fds = [self.rc_fd]
        try:
            if self.password:
                r, w = _safe_pipe()
                os.write(w, self.password.encode())
                os.close(w)
                prefix += ['--password-file', f'fd:{r}', '--use-password', 'always']
                pass_fds.append(r)
            cmd = prefix + ['action', 'move_window', direction]
            is_inheritable = os.get_inheritable(self.rc_fd)
            if not is_inheritable:
                os.set_inheritable(self.rc_fd, True)
            try:
                subprocess.run(cmd, pass_fds=tuple(pass_fds), capture_output=True)
            finally:
                if not is_inheritable:
                    os.set_inheritable(self.rc_fd, False)
        finally:
            if r > -1:
                os.close(r)
        self.draw_screen()

    def on_text(self, text: str, in_bracketed_paste: bool = False) -> None:
        text = text.lower()
        directions = {'l': 'left', 'r': 'right', 'u': 'up', 'd': 'down'}
        if text in directions:
            self.do_move(directions[text])
        elif text == 'q':
            self.quit_loop(0)

    def on_key(self, key_event: KeyEvent) -> None:
        if key_event.type is EventType.RELEASE:
            return
        if key_event.matches('esc'):
            self.quit_loop(0)

    def on_resize(self, new_size: ScreenSize) -> None:
        self.draw_screen()

    def draw_screen(self) -> None:
        self.cmd.clear_screen()
        p = self.print
        p(styled('Move this window', bold=True, fg='gray', fg_intense=True))
        p()
        p('Press one of the following keys:')
        p('  {}eft'.format(styled('L', fg='green')))
        p('  {}ight'.format(styled('R', fg='green')))
        p('  {}p'.format(styled('U', fg='green')))
        p('  {}own'.format(styled('D', fg='green')))
        p()
        p('Press {} to quit move mode'.format(styled('Esc', italic=True)))


def main(args: list[str]) -> None:
    loop = Loop()
    handler = MoveWindow()
    loop.loop(handler)
    if handler.print_on_fail:
        print(handler.print_on_fail, file=sys.stderr)
        input('Press Enter to quit')
    raise SystemExit(loop.return_code)


main.allow_remote_control = True  # type: ignore[attr-defined]

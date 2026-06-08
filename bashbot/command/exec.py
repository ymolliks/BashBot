import asyncio
import os
import signal
import subprocess
import time

from discord.ext import commands

from bashbot.core.settings import settings
from bashbot.core.utils import code_block

EXEC_OUTPUT_LIMIT = 50000


class ExecCommand(commands.Cog):
    @commands.hybrid_command(
        name='exec',
        aliases=['.exec', '.e'],
        description='Execute single command',
        usage='<command...>'
    )
    async def exec(self, ctx, *, command):
        if ctx.interaction:
            await ctx.defer()

        output = await asyncio.to_thread(self._execute, command)
        await ctx.send(code_block(output))

    @staticmethod
    def _execute(command):
        shell_path = settings().get('terminal.shell_path')

        login_as_other_user = settings().get('terminal.user.login_as_other_user')
        if login_as_other_user:
            return ExecCommand._execute_as_user(command, shell_path)

        if not os.path.exists(shell_path):
            return f'Shell path does not exist: {shell_path}'

        timeout = settings().get('terminal.exec_timeout')
        try:
            result = subprocess.run(
                [shell_path, '-c', command],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            output = ExecCommand._join_output(error.stdout, error.stderr)
            return ExecCommand._format_result(output, None, timed_out_after=timeout)

        output = ExecCommand._join_output(result.stdout, result.stderr)
        return ExecCommand._format_result(output, result.returncode)

    @staticmethod
    def _decode(value):
        if value is None:
            return ''
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        return str(value)

    @staticmethod
    def _join_output(stdout, stderr):
        return f'{ExecCommand._decode(stdout)}{ExecCommand._decode(stderr)}'.rstrip()

    @staticmethod
    def _format_result(output, returncode, timed_out_after=None):
        output = output or '(no output)'
        if len(output) > EXEC_OUTPUT_LIMIT:
            output = output[:EXEC_OUTPUT_LIMIT] + '\n... exec output truncated ...'

        lines = [output]
        if timed_out_after is not None:
            lines.append(f'Command timed out after {timed_out_after} seconds')
        elif returncode and returncode != 0:
            lines.append(f'Command exited with status {returncode}')

        return '\n'.join(lines).strip()

    @staticmethod
    def _execute_as_user(command, shell_path):
        import pty

        su_path = settings().get('terminal.su_path')

        login = settings().get('terminal.user.username')
        password = settings().get('terminal.user.password')
        timeout = settings().get('terminal.exec_timeout')

        if not os.path.exists(shell_path):
            return f'Shell path does not exist: {shell_path}'

        if not os.path.exists(su_path):
            return f'su path does not exist: {su_path}'

        master, slave = pty.openpty()
        process = subprocess.Popen(
            [su_path, "-", login, "-s", shell_path, '-c', command],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True
        )
        os.close(slave)

        try:
            os.write(master, f'{password}\n'.encode())
            output = ExecCommand._read_pty_until_exit(master, process, timeout)
            output = output.replace(password, '[redacted]')
            return ExecCommand._format_result(output, process.returncode)
        except TimeoutError:
            ExecCommand._kill_process(process)
            output = ExecCommand._drain_pty(master).replace(password, '[redacted]')
            return ExecCommand._format_result(output, None, timed_out_after=timeout)
        finally:
            if process.poll() is None:
                ExecCommand._kill_process(process)
            os.close(master)

    @staticmethod
    def _read_pty_until_exit(master, process, timeout):
        import select

        chunks = []
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()

            if process.poll() is not None:
                chunks.append(ExecCommand._drain_pty(master))
                return ''.join(chunks).rstrip()

            ready, _, _ = select.select([master], [], [], min(0.1, remaining))
            if not ready:
                continue

            try:
                data = os.read(master, 4096)
            except OSError:
                process.poll()
                return ''.join(chunks).rstrip()

            if not data:
                process.poll()
                return ''.join(chunks).rstrip()

            chunks.append(ExecCommand._decode(data))
            if sum(len(chunk) for chunk in chunks) > EXEC_OUTPUT_LIMIT:
                chunks = [''.join(chunks)[-EXEC_OUTPUT_LIMIT:]]

    @staticmethod
    def _drain_pty(master):
        import select

        chunks = []
        while True:
            ready, _, _ = select.select([master], [], [], 0)
            if not ready:
                break

            try:
                data = os.read(master, 4096)
            except OSError:
                break

            if not data:
                break

            chunks.append(ExecCommand._decode(data))

        return ''.join(chunks).rstrip()

    @staticmethod
    def _kill_process(process):
        try:
            if hasattr(os, 'killpg'):
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except OSError:
            try:
                process.kill()
            except OSError:
                pass

        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass

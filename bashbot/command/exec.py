import asyncio
import os
import subprocess

from discord.ext import commands

from bashbot.core.settings import settings
from bashbot.core.utils import code_block


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

        timeout = settings().get('terminal.exec_timeout')
        try:
            result = subprocess.run(
                [shell_path, '-c', command],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            return f'Shell path does not exist: {shell_path}'
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ''
            error_output = error.stderr or ''
            return f'{output}{error_output}\nCommand timed out after {timeout} seconds'.strip()

        output = f'{result.stdout}{result.stderr}'.rstrip()
        if result.returncode != 0:
            output = f'{output}\nCommand exited with status {result.returncode}'.strip()

        return output

    @staticmethod
    def _execute_as_user(command, shell_path):
        import pty

        su_path = settings().get('terminal.su_path')

        login = settings().get('terminal.user.username')
        password = settings().get('terminal.user.password')

        master, slave = pty.openpty()
        process = subprocess.Popen(
            [su_path, "-", login, "-s", shell_path, '-c', command],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            universal_newlines=True
        )

        try:
            os.read(master, 10240)  # ignore prompt
            os.write(master, f'{password}\n'.encode())
            os.read(master, 10240)  # ignore empty line
            output = os.read(master, 10240).rstrip().decode('utf-8')
            process.wait(timeout=settings().get('terminal.exec_timeout'))
            return output
        finally:
            if process.poll() is None:
                process.kill()
            os.close(master)
            os.close(slave)

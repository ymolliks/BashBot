from discord import Message, Embed
from discord.ext import commands

from bashbot.core.exceptions import ArgumentFormatException
from bashbot.core.macros import execute_macro
from bashbot.core.settings import settings
from bashbot.terminal.sessions import sessions
from bashbot.terminal.terminal import Terminal, TerminalStartupError
from bashbot.core.utils import parse_template


class OpenCommand(commands.Cog):
    @commands.hybrid_command(
        name='open',
        aliases=['.open', '.o'],
        description='Opens new terminal session',
        usage='[name]'
    )
    async def open(self, ctx, name: str = None):
        if name and len(name) > 20:
            raise ArgumentFormatException('Session name length exceeds 20 characters limit')

        if not name:
            name = str(sessions().next_id)

        content = parse_template(
            settings().get('terminal.template'),
            id=sessions().next_id,
            name=name,
            state='OPENING',
            content='Waiting for tty..'
        )
        message: Message = await ctx.send(content)

        sh_path = settings().get('terminal.shell_path')

        login_as_other_user = settings().get('terminal.user.login_as_other_user')
        if login_as_other_user:
            su_path = settings().get('terminal.su_path')
            login = settings().get('terminal.user.username')
            password = settings().get('terminal.user.password')
            terminal = Terminal(
                name,
                sh_path=sh_path,
                on_change=sessions().update_message,
                on_exit=sessions().finish_terminal,
                su_path=su_path,
                login=login,
                password=password
            )
        else:
            terminal = Terminal(
                name,
                sh_path=sh_path,
                on_change=sessions().update_message,
                on_exit=sessions().finish_terminal
            )

        sessions().add(message, terminal)
        try:
            import asyncio
            terminal.open(loop=asyncio.get_running_loop())
        except TerminalStartupError as error:
            sessions().remove(terminal)
            content = parse_template(
                settings().get('terminal.template'),
                id=getattr(terminal, 'session_id', '?'),
                name=name,
                state='BROKEN',
                content=str(error)
            )
            await message.edit(content=content)
            await ctx.send(f'`{error}`')
            return

        startup_macro = settings().get('terminal.startup_macro')
        if startup_macro:
            await execute_macro(ctx, startup_macro)

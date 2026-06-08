import asyncio

from discord import Embed
from discord.ext import commands
from discord.ext.commands import Context

from bashbot.command import session_exists
from bashbot.constants import EMBED_COLOR
from bashbot.core.exceptions import SessionDontExistException
from bashbot.core.settings import settings
from bashbot.core.utils import code_block
from bashbot.terminal.sessions import sessions as terminal_sessions
from bashbot.terminal.terminal import TerminalStartupError, TerminalState


class SessionsCommand(commands.Cog):
    @commands.hybrid_command(
        name='sessions',
        aliases=['.sessions', '.ss', '.ps'],
        description='Lists terminal sessions'
    )
    async def sessions(self, ctx: Context):
        terminals = terminal_sessions().all()
        selected = terminal_sessions().by_channel(ctx.channel)

        if not terminals:
            embed = Embed(description='No terminal sessions are open', color=EMBED_COLOR)
            await ctx.send(embed=embed)
            return

        lines = []
        for terminal in terminals:
            marker = '*' if terminal == selected else ' '
            flags = []
            if terminal.interactive:
                flags.append('interactive')
            if terminal.auto_submit:
                flags.append('auto-submit')

            mode = ', '.join(flags) if flags else 'manual'
            session_id = getattr(terminal, 'session_id', '?')
            lines.append(f'{marker} #{session_id:<3} {terminal.name:<20} {terminal.state.name:<6} {mode}')

        await ctx.send(code_block('\n'.join(lines)))


class KillCommand(commands.Cog):
    @commands.hybrid_command(
        name='kill',
        aliases=['.kill'],
        description='Force terminates current terminal session'
    )
    @session_exists()
    async def kill(self, ctx: Context):
        terminal = terminal_sessions().by_channel(ctx.channel)
        if not terminal:
            raise SessionDontExistException()

        terminal.kill()
        await terminal_sessions().update_message(terminal, terminal.content)
        terminal_sessions().remove(terminal)

        embed = Embed(description=f"Killed terminal #{terminal.name}", color=0xff0000)
        await ctx.send(embed=embed)


class RestartCommand(commands.Cog):
    @commands.hybrid_command(
        name='restart',
        aliases=['.restart'],
        description='Restarts current terminal session'
    )
    @session_exists()
    async def restart(self, ctx: Context):
        terminal = terminal_sessions().by_channel(ctx.channel)
        if not terminal:
            raise SessionDontExistException()

        try:
            terminal.restart(loop=asyncio.get_running_loop())
        except TerminalStartupError as error:
            terminal.state = TerminalState.BROKEN
            await terminal_sessions().update_message(terminal, str(error))
            await ctx.send(f'`{error}`')
            return

        startup_macro = settings().get('terminal.startup_macro')
        if startup_macro:
            from bashbot.core.macros import execute_macro
            await execute_macro(ctx, startup_macro)

        embed = Embed(description=f"Restarted terminal #{terminal.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)

from discord import Embed
from discord.ext import commands
from discord.ext.commands import Context

from bashbot.command import session_exists
from bashbot.constants import EMBED_COLOR
from bashbot.core.exceptions import SessionDontExistException
from bashbot.terminal.sessions import sessions


class ClearCommand(commands.Cog):
    @commands.hybrid_command(
        name='clear',
        aliases=['.clear', '.cls'],
        description='Clears the terminal screen'
    )
    @session_exists()
    async def clear(self, ctx: Context):
        terminal = sessions().by_channel(ctx.channel)

        if not terminal:
            raise SessionDontExistException()

        terminal.send_input('\x0c')
        embed = Embed(description=f"Cleared terminal #{terminal.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)

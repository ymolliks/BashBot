from discord import Embed
from discord.ext import commands

from bashbot.command import session_exists
from bashbot.constants import EMBED_COLOR
from bashbot.terminal.sessions import sessions


class RepostCommand(commands.Cog):
    @commands.hybrid_command(
        name='repost',
        aliases=['.repost', '.rp'],
        description='Moves terminal message to the bottom of chat'
    )
    @session_exists()
    async def repost(self, ctx):
        terminal = sessions().by_channel(ctx.channel)
        await sessions().repost(terminal)
        embed = Embed(description=f"Moved terminal #{terminal.name} to bottom", color=EMBED_COLOR)
        await ctx.send(embed=embed)

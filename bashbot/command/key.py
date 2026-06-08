from discord import Embed
from discord.ext import commands
from discord.ext.commands import Context

from bashbot.command import session_exists
from bashbot.constants import EMBED_COLOR
from bashbot.core.exceptions import SessionDontExistException
from bashbot.terminal.sessions import sessions


class EnterCommand(commands.Cog):
    @commands.hybrid_command(name='enter', aliases=['.enter'], description='Sends Enter/Return to the terminal')
    @session_exists()
    async def enter(self, ctx: Context):
        terminal = sessions().by_channel(ctx.channel)
        if not terminal:
            raise SessionDontExistException()
        terminal.send_input('\n')
        embed = Embed(description=f"Sent Enter to terminal #{terminal.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)


class UpCommand(commands.Cog):
    @commands.hybrid_command(name='up', aliases=['.up'], description='Sends Up arrow to the terminal')
    @session_exists()
    async def up(self, ctx: Context):
        terminal = sessions().by_channel(ctx.channel)
        if not terminal:
            raise SessionDontExistException()
        terminal.send_input('\u001b[A')
        embed = Embed(description=f"Sent Up to terminal #{terminal.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)


class DownCommand(commands.Cog):
    @commands.hybrid_command(name='down', aliases=['.down'], description='Sends Down arrow to the terminal')
    @session_exists()
    async def down(self, ctx: Context):
        terminal = sessions().by_channel(ctx.channel)
        if not terminal:
            raise SessionDontExistException()
        terminal.send_input('\u001b[B')
        embed = Embed(description=f"Sent Down to terminal #{terminal.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)


class LeftCommand(commands.Cog):
    @commands.hybrid_command(name='left', aliases=['.left'], description='Sends Left arrow to the terminal')
    @session_exists()
    async def left(self, ctx: Context):
        terminal = sessions().by_channel(ctx.channel)
        if not terminal:
            raise SessionDontExistException()
        terminal.send_input('\u001b[D')
        embed = Embed(description=f"Sent Left to terminal #{terminal.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)


class RightCommand(commands.Cog):
    @commands.hybrid_command(name='right', aliases=['.right'], description='Sends Right arrow to the terminal')
    @session_exists()
    async def right(self, ctx: Context):
        terminal = sessions().by_channel(ctx.channel)
        if not terminal:
            raise SessionDontExistException()
        terminal.send_input('\u001b[C')
        embed = Embed(description=f"Sent Right to terminal #{terminal.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)

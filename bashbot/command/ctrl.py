from discord import Embed
from discord.ext import commands
from discord.ext.commands import Context

from bashbot.command import session_exists
from bashbot.constants import EMBED_COLOR
from bashbot.core.exceptions import SessionDontExistException
from bashbot.terminal.sessions import sessions

CTRL_CHARS = {
    'c': '\x03',
    'd': '\x04',
    'z': '\x1a',
    'l': '\x0c',
    'a': '\x01',
    'e': '\x05',
    'u': '\x15',
    'w': '\x17',
    'r': '\x12',
    '\\': '\x1c',
}


class CtrlCommand(commands.Cog):
    @commands.hybrid_command(
        name='ctrl',
        aliases=['.ctrl', '.^'],
        description='Sends a control key combination to the terminal',
        usage='<key>'
    )
    @session_exists()
    async def ctrl(self, ctx: Context, key: str):
        terminal = sessions().by_channel(ctx.channel)

        if not terminal:
            raise SessionDontExistException()

        key = key.lower().lstrip('^')
        if key not in CTRL_CHARS:
            valid = ', '.join(f'^{k.upper()}' for k in CTRL_CHARS.keys() if k != '\\')
            embed = Embed(
                title='Invalid control key',
                description=f'Valid keys: {valid}',
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return

        terminal.send_input(CTRL_CHARS[key])
        embed = Embed(description=f"Sent ^^{key.upper()} to terminal #{terminal.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)

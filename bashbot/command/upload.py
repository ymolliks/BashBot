import io
from discord import File, Embed
from discord.ext import commands
from discord.ext.commands import Context

from bashbot.command import session_exists
from bashbot.constants import EMBED_COLOR
from bashbot.core.exceptions import SessionDontExistException
from bashbot.terminal.sessions import sessions


class UploadCommand(commands.Cog):
    @commands.hybrid_command(
        name='upload',
        aliases=['.upload', '.log'],
        description='Uploads current terminal output as a text file'
    )
    @session_exists()
    async def upload(self, ctx: Context):
        terminal = sessions().by_channel(ctx.channel)

        if not terminal:
            raise SessionDontExistException()

        if not terminal.content:
            embed = Embed(description="Terminal has no output yet", color=0xff0000)
            await ctx.send(embed=embed)
            return

        filename = f"terminal_{terminal.name}.txt"
        file = File(fp=io.StringIO(terminal.content), filename=filename)

        embed = Embed(
            description=f"Terminal #{terminal.name} output ({len(terminal.content)} chars)",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed, file=file)

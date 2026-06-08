from discord import Embed, Interaction, app_commands
from discord.ext import commands

from bashbot.constants import EMBED_COLOR
from bashbot.core.exceptions import TerminalNotFoundException
from bashbot.terminal.sessions import sessions


class SelectCommand(commands.Cog):
    @commands.hybrid_command(
        name='select',
        aliases=['.select', '.s'],
        description='Sets terminal as selected',
        usage='<id_or_name>'
    )
    async def select(self, ctx, name):
        terminal = sessions().by_identifier(name)
        if not terminal:
            raise TerminalNotFoundException()

        sessions().select(ctx.channel, terminal)
        session_id = getattr(terminal, 'session_id', '?')
        embed = Embed(description=f"Selected terminal #{session_id} ({terminal.name})", color=EMBED_COLOR)
        await ctx.send(embed=embed)

    @select.autocomplete('name')
    async def select_autocomplete(self, interaction: Interaction, current: str):
        results = sessions().search(current)[:25]
        return [
            app_commands.Choice(name=f'#{getattr(option, "session_id", "?")} {option.name}', value=str(getattr(option, 'session_id', option.name)))
            for option in results
        ]

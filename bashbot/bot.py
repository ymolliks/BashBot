from discord import Message, Status, Game, DMChannel, Embed, Interaction, InteractionType, app_commands
from discord.abc import PrivateChannel
from discord.ext import commands
from discord.ext.commands import Bot, Context
from discord.ui import View, Button
from discord.utils import oauth_url

from bashbot.command.about import AboutCommand
from bashbot.command.clear import ClearCommand
from bashbot.command.ctrl import CtrlCommand
from bashbot.command.exec import ExecCommand
from bashbot.command.close import CloseCommand
from bashbot.command.controls import ControlsCommand
from bashbot.command.freeze import FreezeCommand
from bashbot.command.here import HereCommand
from bashbot.command.interactive import InteractiveCommand
from bashbot.command.key import EnterCommand, UpCommand, DownCommand, LeftCommand, RightCommand
from bashbot.command.macro import MacroCommand
from bashbot.command.open import OpenCommand
from bashbot.command.rename import RenameCommand
from bashbot.command.repeat import RepeatCommand
from bashbot.command.repost import RepostCommand
from bashbot.command.select import SelectCommand
from bashbot.command.session import KillCommand, RestartCommand, SessionsCommand
from bashbot.command.submit import SubmitCommand
from bashbot.command.upload import UploadCommand
from bashbot.command.help import HelpCommand
from bashbot.command.whitelist import WhitelistCommand
from bashbot.core.exceptions import SessionDontExistException, ArgumentFormatException, TerminalNotFoundException, \
    MacroNotFoundException
from bashbot.core.settings import settings
from bashbot.core.state import state
from bashbot.terminal.sessions import sessions
from bashbot.terminal.terminal import TerminalState
from bashbot.core.updater import updater, Updater
from bashbot.core.utils import get_logger, parse_template, extract_prefix, is_command, remove_prefix


class BashBot(Bot):
    logger = get_logger('BashBot')
    cmd_logger = get_logger('Command')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._command_tree_sync_checked = False
        self.add_check(self.check_context_permissions, call_once=True)

    async def setup_hook(self):
        self.tree.interaction_check = self.check_interaction_permissions
        self.tree.on_error = self.on_app_command_error

        await self.add_cog(OpenCommand())
        await self.add_cog(CloseCommand())
        await self.add_cog(HereCommand())
        await self.add_cog(FreezeCommand())
        await self.add_cog(RenameCommand())
        await self.add_cog(ControlsCommand())
        await self.add_cog(AboutCommand())
        await self.add_cog(ClearCommand())
        await self.add_cog(CtrlCommand())
        await self.add_cog(UploadCommand())
        await self.add_cog(RepeatCommand())
        await self.add_cog(RepostCommand())
        await self.add_cog(MacroCommand())
        await self.add_cog(SelectCommand())
        await self.add_cog(SessionsCommand())
        await self.add_cog(KillCommand())
        await self.add_cog(RestartCommand())
        await self.add_cog(InteractiveCommand())
        await self.add_cog(EnterCommand())
        await self.add_cog(UpCommand())
        await self.add_cog(DownCommand())
        await self.add_cog(LeftCommand())
        await self.add_cog(RightCommand())
        await self.add_cog(SubmitCommand())
        await self.add_cog(ExecCommand())
        await self.add_cog(WhitelistCommand())

        self.remove_command("help")
        await self.add_cog(HelpCommand())

    async def on_ready(self):
        await self.__sync_command_tree_once()
        await self.__check_for_updates()

        self.logger.info(f'Logged in as {self.user.name} ({self.user.id})')
        self.logger.info(f'You can add bot to your server via {oauth_url(self.user.id)}')

        first_prefix = settings().get('commands.prefixes', ['$'])[0]
        presence = parse_template(
            settings().get("discord.presence"),
            prefix=first_prefix
        )
        await self.change_presence(
            status=Status.online,
            activity=Game(presence)
        )

    async def __sync_command_tree_once(self):
        if self._command_tree_sync_checked:
            return

        self._command_tree_sync_checked = True
        local_version = Updater.get_local_commit()
        last_synced_version = state().get('last_command_sync_version')
        if last_synced_version and last_synced_version == local_version:
            return

        try:
            self.logger.info('Synchronizing command tree...')
            await self.tree.sync()
        except Exception:
            self.logger.exception('Failed to synchronize command tree')
            return

        state()['last_command_sync_version'] = local_version
        state()['last_run_version'] = local_version
        state().save()
        self.logger.info('Command tree synchronized')

    async def __check_for_updates(self):
        if settings().get('other.check_for_updates'):
            self.logger.info('Checking for updates...')

            releases = await updater().check_for_updates_async()
            if releases is None:
                self.logger.info('Failed to fetch updates information')
            elif releases:
                self.logger.info(
                    'New updates available. Try running `git pull`. \n' +
                    '\n'.join([f'- {x["name"]} ({x["html_url"]})' for x in releases])
                )
            else:
                self.logger.info('BashBot is up to date')

    async def check_context_permissions(self, ctx: Context):
        return await self.check_message_permissions(ctx.message)

    async def check_message_permissions(self, message: Message):
        async def send(embed):
            await message.channel.send(embed=embed)

        return await self.__check_permissions(
            user=message.author,
            channel=message.channel,
            send=send
        )

    async def check_interaction_permissions(self, interaction: Interaction):
        async def send(embed):
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

        return await self.__check_permissions(
            user=interaction.user,
            channel=interaction.channel,
            send=send
        )

    async def __check_permissions(self, user, channel, send):
        is_owner = await self.is_owner(user)
        if is_owner:
            return True

        if settings().get('discord.enable_users_whitelist'):
            users_whitelist = settings().get('discord.users_whitelist', [])

            if user.id not in users_whitelist:
                first_prefix = settings().get('commands.prefixes')[0]
                embed = Embed(
                    title='Only whitelisted users can execute commands',
                    description=f'Ask the bot owner to run `/whitelist add` or `{first_prefix}.whitelist add {user.mention}`'
                )

                await send(embed)
                return False

        if isinstance(channel, PrivateChannel) and settings().get('discord.disable_dm'):
            embed = Embed(
                title='Using bot on DM is disabled',
                description='discord.disable_dm = true'
            )

            await send(embed)
            return False

        return True

    async def on_message(self, message: Message):
        if message.author.bot:
            return

        terminal = sessions().by_channel(message.channel)

        if self.is_invoke(message):
            await self.process_commands(message)
        elif terminal and terminal.state == TerminalState.OPEN:
            prefix = extract_prefix(message.content)
            if not terminal.interactive and not prefix and not terminal.auto_submit:
                return

            if not await self.check_message_permissions(message):
                return

            # We don't remove prefix when in interactive mode.
            content = message.content
            if not terminal.interactive and prefix:
                content = remove_prefix(content)

            if terminal.auto_submit:
                content += '\n'

            terminal.send_input(content)

            guild = getattr(message.channel, 'guild', None)
            guild_name = getattr(guild, 'name', 'DM')
            channel_name = getattr(message.channel, 'name', 'DM')
            author_name = message.author.name
            self.cmd_logger.info(f"[{guild_name}/#{channel_name}/{terminal.name}] {author_name} typed: {content}")

            should_delete_any = settings().get('terminal.delete_messages')
            should_delete_interactive = settings().get('terminal.interactive.delete_messages')
            if should_delete_any or (should_delete_interactive and terminal.interactive):
                await message.delete()

            if settings().get('terminal.auto_repost'):
                terminal._repost_requested = True

    async def on_interaction(self, interaction: Interaction):
        if interaction.type != InteractionType.component or not interaction.message:
            return

        custom_id = interaction.data.get('custom_id', '')
        if not custom_id.startswith('control_'):
            return

        terminal = sessions().by_message(interaction.message)
        if terminal:
            return

        if not interaction.response.is_done():
            await interaction.response.send_message(content='This terminal is unavailable', ephemeral=True)

        view = View.from_message(interaction.message)
        for component in view.children:
            if isinstance(component, Button):
                component.disabled = True

        await interaction.message.edit(view=view)

    async def on_command(self, ctx: Context):
        if not isinstance(ctx.message.channel, DMChannel):
            guild_name = ctx.message.channel.guild.name
            channel_name = ctx.message.channel.name
        else:
            guild_name = 'DM'
            channel_name = 'DM'

        author_name = ctx.message.author.name
        content = ctx.message.content

        self.cmd_logger.info(f"[{guild_name}/#{channel_name}] {author_name} invoked command: {content}")

    async def on_command_error(self, ctx: Context, error):
        message = self.__friendly_error_message(error)

        if message:
            await ctx.send(f'`{message}`')

    async def on_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        message = self.__friendly_error_message(error)

        if message:
            if interaction.response.is_done():
                await interaction.followup.send(content=f'`{message}`', ephemeral=True)
            else:
                await interaction.response.send_message(content=f'`{message}`', ephemeral=True)
            return

        self.logger.exception('Unhandled app command error', exc_info=error)

    @staticmethod
    def __friendly_error_message(error):
        original = getattr(error, 'original', error)
        handled_errors = (
            ArgumentFormatException,
            SessionDontExistException,
            TerminalNotFoundException,
            MacroNotFoundException,
        )

        if isinstance(original, handled_errors):
            return original.message

    def is_invoke(self, message: Message):
        if isinstance(message.channel, PrivateChannel):
            return True

        has_mention = self.user in message.mentions if self.user else False
        return is_command(message.content) or has_mention

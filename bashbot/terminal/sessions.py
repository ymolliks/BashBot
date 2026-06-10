from typing import List, TYPE_CHECKING

from bashbot.core.factory import SingletonDecorator
from bashbot.core.settings import settings
from bashbot.core.utils import DISCORD_MESSAGE_LIMIT, get_logger, parse_template, block_escape

if TYPE_CHECKING:
    from discord import Message, TextChannel

    from bashbot.terminal.terminal import Terminal


class Sessions:
    logger = get_logger('Sessions')

    def __init__(self):
        self.sessions = {}
        self.selected = {}
        self.next_id = 1

    @staticmethod
    def _message_key(message):
        return getattr(message, 'id', id(message))

    @staticmethod
    def _channel_key(channel):
        return getattr(channel, 'id', id(channel))

    def _assign_id(self, terminal: 'Terminal'):
        if getattr(terminal, 'session_id', None) is None:
            terminal.session_id = self.next_id
            self.next_id += 1

    def add(self, message: 'Message', terminal: 'Terminal'):
        self._assign_id(terminal)
        self.sessions[self._message_key(message)] = (message, terminal)
        self.select(message.channel, terminal)

    def select(self, channel: 'TextChannel', terminal: 'Terminal'):
        self.selected[self._channel_key(channel)] = terminal

    def by_channel(self, channel: 'TextChannel') -> 'Terminal':
        return self.selected.get(self._channel_key(channel))

    def by_message(self, searched_message: 'Message') -> 'Terminal':
        binding = self.sessions.get(self._message_key(searched_message))
        if binding:
            return binding[1]

    def search(self, phrase: str) -> List['Terminal']:
        phrase = str(phrase)
        return [
            terminal
            for _, terminal in self.sessions.values()
            if terminal.name.startswith(phrase) or str(getattr(terminal, 'session_id', '')).startswith(phrase)
        ]

    def by_name(self, name: str) -> 'Terminal':
        for _, terminal in self.sessions.values():
            if terminal.name == name:
                return terminal

    def by_identifier(self, identifier: str) -> 'Terminal':
        identifier = str(identifier).lstrip('#')
        if identifier.isdigit():
            session_id = int(identifier)
            for _, terminal in self.sessions.values():
                if getattr(terminal, 'session_id', None) == session_id:
                    return terminal

        return self.by_name(identifier)

    def all(self) -> List['Terminal']:
        terminals = [terminal for _, terminal in self.sessions.values()]
        return sorted(terminals, key=lambda terminal: getattr(terminal, 'session_id', 0))

    def remove(self, terminal: 'Terminal'):
        for message_id, (_, stored_terminal) in self.sessions.copy().items():
            if stored_terminal == terminal:
                del self.sessions[message_id]

        for channel_id, selected_terminal in self.selected.copy().items():
            if selected_terminal == terminal:
                del self.selected[channel_id]

    def find_message(self, terminal: 'Terminal'):
        for message, stored_terminal in self.sessions.values():
            if stored_terminal == terminal:
                return message

    def update_message_reference(self, terminal: 'Terminal', message: 'Message'):
        old_message = self.find_message(terminal)
        if old_message:
            del self.sessions[self._message_key(old_message)]

        self.sessions[self._message_key(message)] = (message, terminal)

    @staticmethod
    def render_message(terminal: 'Terminal', content: str, limit=DISCORD_MESSAGE_LIMIT):
        template = settings().get('terminal.template', '`| TTY #{id}:{name} | {state} |`\n```{content}```')
        escaped_content = block_escape(content)

        def render(content_value):
            return parse_template(
                template,
                id=getattr(terminal, 'session_id', '?'),
                name=terminal.name,
                state=terminal.state.name,
                content=content_value
            )

        rendered = render(escaped_content)
        if len(rendered) <= limit:
            return rendered

        static_rendered = render('')
        available = limit - len(static_rendered)
        if available <= 0:
            return static_rendered[:limit]

        marker = '\n... output truncated ...'
        clipped_content = escaped_content[:available - len(marker)] + marker

        rendered = render(clipped_content)
        while len(rendered) > limit and len(clipped_content) > len(marker):
            overage = len(rendered) - limit
            clipped_content = clipped_content[:len(clipped_content) - overage - len(marker)] + marker
            rendered = render(clipped_content)

        return rendered[:limit]

    async def update_message(self, terminal: 'Terminal', content: str):
        message = self.find_message(terminal)
        if not message:
            return

        content = self.render_message(terminal, content)

        try:
            await message.edit(content=content, embed=None)
        except Exception:
            self.logger.exception('Failed to update terminal message')

        if getattr(terminal, '_repost_requested', False):
            terminal._repost_requested = False
            await self.repost(terminal)

    async def repost(self, terminal: 'Terminal'):
        old_message = self.find_message(terminal)
        if not old_message:
            return

        try:
            content = self.render_message(terminal, terminal.content)
            new_message = await old_message.channel.send(content=content)
        except Exception:
            self.logger.exception('Failed to repost terminal message')
            return

        self.remove(terminal)
        self.add(new_message, terminal)
        try:
            await old_message.delete()
        except Exception:
            pass

    async def finish_terminal(self, terminal: 'Terminal', content: str):
        await self.update_message(terminal, content)
        self.remove(terminal)


sessions = SingletonDecorator(Sessions)

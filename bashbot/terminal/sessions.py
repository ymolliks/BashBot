from typing import List, TYPE_CHECKING

from bashbot.core.factory import SingletonDecorator
from bashbot.core.settings import settings
from bashbot.core.utils import parse_template, block_escape

if TYPE_CHECKING:
    from discord import Message, TextChannel

    from bashbot.terminal.terminal import Terminal


class Sessions:
    def __init__(self):
        self.sessions = {}
        self.selected = {}

    @staticmethod
    def _message_key(message):
        return getattr(message, 'id', id(message))

    @staticmethod
    def _channel_key(channel):
        return getattr(channel, 'id', id(channel))

    def add(self, message: 'Message', terminal: 'Terminal'):
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
        return [
            terminal
            for _, terminal in self.sessions.values()
            if terminal.name.startswith(phrase)
        ]

    def by_name(self, name: str) -> 'Terminal':
        for _, terminal in self.sessions.values():
            if terminal.name == name:
                return terminal

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

    async def update_message(self, terminal: 'Terminal', content: str):
        message = self.find_message(terminal)
        if not message:
            return

        content = parse_template(
            settings().get('terminal.template'),
            name=terminal.name,
            state=terminal.state.name,
            content=block_escape(content)
        )

        await message.edit(content=content, embed=None)


sessions = SingletonDecorator(Sessions)

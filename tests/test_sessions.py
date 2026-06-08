import asyncio
import unittest

from bashbot.core.settings import settings
from bashbot.terminal.sessions import Sessions
from bashbot.terminal.terminal import TerminalState


class FakeChannel:
    def __init__(self, channel_id):
        self.id = channel_id


class FakeMessage:
    def __init__(self, message_id, channel):
        self.id = message_id
        self.channel = channel


class EditableFakeMessage(FakeMessage):
    def __init__(self, message_id, channel):
        super().__init__(message_id, channel)
        self.edited_content = None

    async def edit(self, content=None, embed=None):
        self.edited_content = content
        return self


class FakeTerminal:
    def __init__(self, name):
        self.session_id = None
        self.name = name
        self.state = TerminalState.OPEN


class SessionsTests(unittest.TestCase):
    def test_tracks_sessions_by_discord_ids(self):
        sessions = Sessions()
        channel = FakeChannel(10)
        first_message = FakeMessage(20, channel)
        same_message_from_event = FakeMessage(20, channel)
        terminal = FakeTerminal('main')

        sessions.add(first_message, terminal)

        self.assertIs(sessions.by_channel(channel), terminal)
        self.assertIs(sessions.by_message(same_message_from_event), terminal)
        self.assertIs(sessions.by_name('main'), terminal)
        self.assertIs(sessions.by_identifier('1'), terminal)
        self.assertEqual(terminal.session_id, 1)

    def test_update_message_reference_preserves_terminal(self):
        sessions = Sessions()
        channel = FakeChannel(10)
        old_message = FakeMessage(20, channel)
        new_message = FakeMessage(21, channel)
        terminal = FakeTerminal('main')

        sessions.add(old_message, terminal)
        sessions.update_message_reference(terminal, new_message)

        self.assertIsNone(sessions.by_message(old_message))
        self.assertIs(sessions.by_message(new_message), terminal)

    def test_remove_clears_selected_channels(self):
        sessions = Sessions()
        channel = FakeChannel(10)
        message = FakeMessage(20, channel)
        terminal = FakeTerminal('main')

        sessions.add(message, terminal)
        sessions.remove(terminal)

        self.assertIsNone(sessions.by_channel(channel))
        self.assertIsNone(sessions.by_message(message))

    def test_all_returns_sessions_ordered_by_id(self):
        sessions = Sessions()
        channel = FakeChannel(10)
        first = FakeTerminal('first')
        second = FakeTerminal('second')

        sessions.add(FakeMessage(20, channel), second)
        sessions.add(FakeMessage(21, channel), first)

        self.assertEqual(sessions.all(), [second, first])

    def test_render_message_respects_limit_and_keeps_tail(self):
        singleton = settings()
        original_config = singleton.config
        singleton.config = {
            'terminal': {
                'template': '`| TTY #{id}:{name} | {state} |`\n```{content}```',
            },
        }
        terminal = FakeTerminal('main')
        terminal.session_id = 7

        try:
            rendered = Sessions.render_message(terminal, 'a' * 200 + 'THE_END', limit=100)
        finally:
            singleton.config = original_config

        self.assertLessEqual(len(rendered), 100)
        self.assertIn('output truncated', rendered)
        self.assertIn('THE_END', rendered)
        self.assertIn('#7:main', rendered)

    def test_finish_terminal_updates_then_removes_session(self):
        sessions = Sessions()
        channel = FakeChannel(10)
        message = EditableFakeMessage(20, channel)
        terminal = FakeTerminal('main')
        terminal.state = TerminalState.CLOSED

        sessions.add(message, terminal)
        asyncio.run(sessions.finish_terminal(terminal, 'done'))

        self.assertIn('CLOSED', message.edited_content)
        self.assertIsNone(sessions.by_message(message))
        self.assertIsNone(sessions.by_channel(channel))


if __name__ == '__main__':
    unittest.main()

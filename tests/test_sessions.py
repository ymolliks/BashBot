import unittest

from bashbot.terminal.sessions import Sessions


class FakeChannel:
    def __init__(self, channel_id):
        self.id = channel_id


class FakeMessage:
    def __init__(self, message_id, channel):
        self.id = message_id
        self.channel = channel


class FakeTerminal:
    def __init__(self, name):
        self.name = name


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


if __name__ == '__main__':
    unittest.main()

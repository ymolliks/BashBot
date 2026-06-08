import unittest
from unittest.mock import patch

from bashbot.core.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_get_preserves_falsy_values(self):
        settings = Settings()
        settings.config = {
            'feature': {
                'enabled': False,
                'count': 0,
                'name': '',
            }
        }

        self.assertIs(settings.get('feature.enabled', True), False)
        self.assertEqual(settings.get('feature.count', 10), 0)
        self.assertEqual(settings.get('feature.name', 'fallback'), '')
        self.assertEqual(settings.get('feature.missing', 'fallback'), 'fallback')

    def test_load_adds_new_defaults(self):
        settings = Settings()
        config_path = 'tests/does-not-exist-for-settings-test.toml'

        with patch.object(settings, 'save') as save:
            settings.load(config_path)

        self.assertTrue(settings.get('discord.message_content_intent'))
        self.assertEqual(settings.get('terminal.exec_timeout'), 30)
        save.assert_called_once_with(config_path)


if __name__ == '__main__':
    unittest.main()

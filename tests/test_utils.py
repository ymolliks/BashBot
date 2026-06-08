import unittest

from bashbot.core.utils import block_escape, code_block
from bashbot.terminal.shortcuts import replace_shortcuts


class UtilsTests(unittest.TestCase):
    def test_block_escape_breaks_code_fences(self):
        escaped = block_escape('before ``` after')

        self.assertNotIn('```', escaped)
        self.assertIn('before', escaped)
        self.assertIn('after', escaped)

    def test_code_block_respects_limit(self):
        rendered = code_block('x' * 100, limit=30)

        self.assertLessEqual(len(rendered), 30)
        self.assertIn('output truncated', rendered)

    def test_shortcuts_replace_arrow_and_control_keys(self):
        self.assertEqual(replace_shortcuts('[UP]'), '\u001b[A')
        self.assertEqual(replace_shortcuts('^C'), '\x03')


if __name__ == '__main__':
    unittest.main()

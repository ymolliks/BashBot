import os
from pathlib import Path

from bashbot.constants import DEFAULT_CONFIG_PATH, DEFAULT_MACRO_PATH
from bashbot.core.factory import SingletonDecorator

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

try:
    import toml
except ModuleNotFoundError:
    toml = None


def _format_toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'

    if isinstance(value, str):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    if isinstance(value, list):
        return '[' + ', '.join(_format_toml_value(item) for item in value) + ']'

    return str(value)


def _write_toml_section(lines, section_path, values):
    scalars = {
        key: value
        for key, value in values.items()
        if not isinstance(value, dict)
    }
    tables = {
        key: value
        for key, value in values.items()
        if isinstance(value, dict)
    }

    if section_path:
        lines.append(f'[{section_path}]')

    for key, value in scalars.items():
        lines.append(f'{key} = {_format_toml_value(value)}')

    if scalars:
        lines.append('')

    for key, value in tables.items():
        next_section = f'{section_path}.{key}' if section_path else key
        _write_toml_section(lines, next_section, value)


def _dump_toml(config):
    if toml:
        return toml.dumps(config)

    lines = []
    _write_toml_section(lines, '', config)
    return '\n'.join(lines).rstrip() + '\n'


def _load_toml(path):
    if toml:
        return toml.load(path)

    if tomllib is None:
        raise RuntimeError('Install toml or use Python 3.11+ to read config.toml')

    with open(path, 'rb') as file:
        return tomllib.load(file)


class Settings:
    def __init__(self):
        self.config: dict = {}
        self.macros: dict = {}

    def load(self, path=DEFAULT_CONFIG_PATH):
        if os.path.exists(path):
            self.config = _load_toml(path)

        # [commands]
        self.add_default('commands.prefixes', ['$', '.bash'])

        # [discord]
        self.add_default('discord.token', 'TOKEN_HERE')
        self.add_default('discord.presence', '{prefix}.help')
        self.add_default('discord.disable_dm', True)
        self.add_default('discord.enable_users_whitelist', True)
        self.add_default('discord.users_whitelist', [])
        self.add_default('discord.message_content_intent', True)

        # [terminal]
        self.add_default('terminal.template', '`| TTY #{id}:{name} | {state} |`\n```{content}```')
        self.add_default('terminal.shell_path', '/bin/bash')
        self.add_default('terminal.su_path', '/bin/su')
        self.add_default('terminal.startup_macro', '')
        self.add_default('terminal.delete_on_close', False)
        self.add_default('terminal.delete_messages', True)
        self.add_default('terminal.submit_by_default', True)
        self.add_default('terminal.interactive_by_default', False)
        self.add_default('terminal.max_refresh_frequency', 0.5)
        self.add_default('terminal.exec_timeout', 30)
        self.add_default('terminal.auto_repost', True)
        self.add_default('terminal.cols', 120)
        self.add_default('terminal.rows', 40)
        self.add_default('terminal.term', 'xterm-256color')

        # [terminal.interactive]
        self.add_default('terminal.interactive.delete_messages', True)

        # [terminal.user]
        self.add_default('terminal.user.login_as_other_user', False)
        self.add_default('terminal.user.username', 'myuser')
        self.add_default('terminal.user.password', 'mypassword')

        # [other]
        self.add_default('other.check_for_updates', True)

        self.save(path)

    def load_macros(self, path=DEFAULT_MACRO_PATH):
        os.makedirs(path, exist_ok=True)

        for filename in os.listdir(path):
            if filename.endswith('.txt'):
                self.macros[filename[:-4]] = Path(path + '/' + filename).read_text(encoding='utf-8')

    def get(self, config_path, default=None):
        current_node = self.config

        # Follow dot path
        for node_name in config_path.split('.'):
            if node_name not in current_node.keys():
                return default

            current_node = current_node[node_name]

        return current_node

    def add_default(self, path, value):
        current_node = self.config
        parts = path.split('.')

        for node_name in parts[:-1]:
            if node_name not in current_node.keys():
                current_node[node_name] = {}

            current_node = current_node[node_name]

        if not parts[-1] in current_node:
            current_node[parts[-1]] = value

    def save(self, path=DEFAULT_CONFIG_PATH):
        with open(path, 'w') as file:
            file.write(_dump_toml(self.config))


settings = SingletonDecorator(Settings)

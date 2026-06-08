import asyncio
import logging

from bashbot.core.settings import settings

DISCORD_MESSAGE_LIMIT = 2000


def get_logger(name):
    logger = logging.getLogger(name)

    if any(isinstance(handler, logging.FileHandler) for handler in logger.handlers):
        return logger

    handler = logging.FileHandler('bashbot.log')
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def parse_template(template, **kwargs):
    for key, value in kwargs.items():
        template = template.replace('{' + key + '}', str(value))

    return template


def execute_async(loop, coroutine):
    asyncio.run_coroutine_threadsafe(coroutine, loop)


def block_escape(text):
    if text is None:
        return ''

    zero_width_mark = '\u200e'
    return str(text).replace('```', f'`{zero_width_mark}`{zero_width_mark}`')


def code_block(content, language='', limit=DISCORD_MESSAGE_LIMIT):
    content = block_escape(content)
    language = language or ''
    wrapper_size = len(f'```{language}\n\n```')
    max_content_length = max(limit - wrapper_size, 0)

    if len(content) > max_content_length:
        suffix = '\n... output truncated ...'
        if len(suffix) >= max_content_length:
            content = suffix[:max_content_length]
        else:
            content = content[:max_content_length - len(suffix)] + suffix

    return f'```{language}\n{content}\n```'


def extract_prefix(content):
    for prefix in settings().get('commands.prefixes'):
        if content.startswith(prefix):
            return prefix


def remove_prefix(content):
    prefix = extract_prefix(content)
    if prefix:
        return content[len(prefix):]
    else:
        return content


def is_command(content):
    return any(content.startswith(prefix + '.') for prefix in settings().get('commands.prefixes'))

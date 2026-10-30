"""Keep command output working whatever encoding the console or pipe uses.

Windows writes redirected output in the ANSI code page, such as cp1252, which
cannot encode every character a job title, article title or file name may
hold. A command that prints one of them used to stop with UnicodeEncodeError
and exit 1 on correct input.
"""

import json
import sys


def configure():
    """Escape characters the output encoding cannot show instead of failing.

    A UTF-8 console is unaffected: every character it can encode is printed
    exactly as before.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")


def dump_json(data, indent=2, stream=None):
    """Print data as JSON that stays valid on any output encoding.

    Text is printed as itself when the stream can encode it, and as JSON
    escapes otherwise. An escaping error handler would turn an astral
    character into \\U0001f600, which is not valid JSON.
    """
    stream = sys.stdout if stream is None else stream
    text = json.dumps(data, ensure_ascii=False, indent=indent)
    try:
        text.encode(getattr(stream, "encoding", None) or "utf-8")
    except (UnicodeEncodeError, LookupError):
        text = json.dumps(data, ensure_ascii=True, indent=indent)
    print(text, file=stream)

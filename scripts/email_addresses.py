"""Shared ASCII email syntax and context-aware public-contact extraction."""
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

ATOM_CHARACTERS = r"A-Za-z0-9!#$%&'*+/=?^_`{|}~\-"
ATOM = "[" + ATOM_CHARACTERS + "]+"
DNS_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
CANDIDATE = re.compile(r"[" + ATOM_CHARACTERS + r".]+@[A-Za-z0-9.-]+")
MAILTO = re.compile(r"(?i)(?<![A-Za-z0-9])mailto:[^\s<>\"')\]]+")


def validate_email_address(value):
    """Validate the supported ASCII dot-atom address, not deliverability."""
    if not isinstance(value, str) or not value.isascii() or len(value) > 254 or value.count("@") != 1:
        raise ValueError("EMAIL must be an ASCII address of at most 254 characters")
    local, domain = value.split("@")
    if len(local) > 64 or not re.fullmatch(ATOM + r"(?:\." + ATOM + r")*", local):
        raise ValueError("EMAIL local part must be a dot-atom of at most 64 characters")
    labels = domain.split(".")
    if len(domain) > 253 or len(labels) < 2 or not all(re.fullmatch(DNS_LABEL, label) for label in labels):
        raise ValueError("EMAIL domain must contain nonempty DNS labels of at most 63 characters without edge hyphens")


def address_key(value):
    local, domain = value.rsplit("@", 1)
    return local, domain.lower()


def text_addresses(text):
    """Find complete candidates without narrowing the accepted atom alphabet."""
    for match in CANDIDATE.finditer(text):
        value = match[0].rstrip(".")
        # Source Markdown can wrap a contact in emphasis or code delimiters.
        # Strip only a matching pair outside the complete address.
        after = text[match.end():]
        for delimiter in ("**", "__", "*", "_", "`", "'"):
            closes = after.startswith(delimiter)
            if delimiter in {"**", "__"}:
                closes = delimiter in after.split("\n\n", 1)[0]
            if value.startswith(delimiter) and closes:
                value = value[len(delimiter):]
                break
        yield value


def contact_values(source, suffix):
    """Return prose candidates and explicit routes, decoding only their context."""
    prose, explicit = [], []

    def structured(value, key=None):
        if isinstance(value, dict):
            for child_key, child in value.items():
                structured(child, child_key)
        elif isinstance(value, list):
            for child in value:
                structured(child, key)
        elif isinstance(value, str):
            (explicit if key == "email" else prose).append(value)

    class ContactHTML(HTMLParser):
        blocks = {"p", "div", "li", "header", "footer", "h1", "h2", "h3", "h4", "td", "th", "tr", "br", "nav", "body", "main", "section"}

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.script = None
            self.skip = False
            self.text = []

        def flush(self):
            if self.text:
                prose.append("".join(self.text))
                self.text = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag in self.blocks:
                self.flush()
            if tag in {"script", "style"}:
                self.flush()
                self.skip = True
                self.script = "" if tag == "script" and values.get("type", "").lower() == "application/ld+json" else None
            target = values.get("href", "")
            if target.lower().startswith("mailto:"):
                try:
                    # Decode only this URI path, once. A literal %2F local part
                    # is encoded as %252F and must remain %2F after decoding.
                    explicit.append(unquote(urlsplit(target).path))
                except ValueError:
                    explicit.append(target)
            for key in ("content", "title", "alt"):
                if values.get(key):
                    prose.append(values[key])

        def handle_data(self, data):
            if self.script is not None:
                self.script += data
            elif not self.skip:
                self.text.append(data)

        def handle_endtag(self, tag):
            if tag in self.blocks:
                self.flush()
            if tag in {"script", "style"}:
                if self.script is not None:
                    try:
                        structured(json.loads(self.script))
                    except ValueError:
                        pass  # The structured-data gate reports malformed JSON.
                self.script, self.skip = None, False

        def close(self):
            super().close()
            self.flush()

    if suffix == ".html":
        parser = ContactHTML()
        parser.feed(source)
        parser.close()
    elif suffix == ".xml":
        try:
            prose.extend(ET.fromstring(source).itertext())
        except ET.ParseError:
            pass
    else:
        prose.append(html.unescape(source))
    addresses = []
    for text in prose:
        def route(match):
            try:
                explicit.append(unquote(urlsplit(match[0]).path))
            except ValueError:
                explicit.append(match[0])
            return " "
        # Markdown/text links are URI contexts too. Never decode other prose.
        addresses.extend(text_addresses(MAILTO.sub(route, text)))
    return addresses, explicit

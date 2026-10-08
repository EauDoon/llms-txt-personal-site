"""Recognize reference-identity markers without spelling them in the tree.

The generic starter (template/, example/, the sample config and the eval data)
must not carry the identity of the site this template was extracted from. The
tests only need to recognize those markers, so this module stores SHA-256
digests of them instead of the markers themselves. That keeps the markers out
of the public tree as searchable text. Digests of short strings are not secret,
because anyone can confirm a guess against them; this is hygiene, not
confidentiality.

This file has no test_ prefix, so unittest discovery does not collect it. Test
modules import it after putting the tests directory on sys.path.
"""
from __future__ import annotations

import hashlib
import re

# Byte length of a normalized marker -> SHA-256 hex digests of the markers of
# that length. A marker is normalized like scanned data: lower-cased, with
# whitespace, underscores and hyphens removed.
MARKER_DIGESTS: dict[int, frozenset[str]] = {
    4: frozenset({
        "040974aabfd1c69105a5a341c6665bf80a7e754e1fcdd2244e8adb5369b75abb",
        "b0442c88eea3fe5d13c2f0a3c5f22e55e23cb34014d20c635246e1b0646ad8e4",
    }),
    7: frozenset({
        "5a8a269390a7dca1720c2382db49329a2ed4aaa4fc3dfc709043096dc0bab872",
    }),
    8: frozenset({
        "324ffbadc4c9f7751aeee92b5a18b700afe2bc3e5eb503fc91b87ec934c3035e",
    }),
    9: frozenset({
        "2171c20d50c482a32e0ddac6f0dcafb483045070cb3fd1dc474a474ff1e91f0d",
    }),
}


def compact(data: bytes) -> bytes:
    """Apply the normalization that markers were hashed under."""
    return re.sub(rb"[\s_-]+", b"", data.lower())


def contains_marker(data: bytes) -> bool:
    """Return whether any normalized window of data hashes to a marker digest."""
    text = compact(data)
    for length, digests in MARKER_DIGESTS.items():
        windows = {text[index:index + length] for index in range(len(text) - length + 1)}
        if any(hashlib.sha256(window).hexdigest() in digests for window in windows):
            return True
    return False

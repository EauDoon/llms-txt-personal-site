# Adversarial quality check. Run before every deploy.
#
# Reads site/ (built by scripts/build.py) and site.config.json.
#
#   python scripts/quality_check.py           local build output only (fast)
#   python scripts/quality_check.py --live    also verify every link and sitemap URL over HTTP
#
# Design note: an earlier version of this reported five failures that were all
# its own false positives. A checker that cries wolf trains you to ignore it,
# which is worse than having none. Every rule below is therefore scoped to the
# thing it actually forbids, and the deliberate exceptions are named in code.
import json
import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlsplit

from a2a_agent_card import load_agent_card, validate_agent_card
from build import BINARY_SUFFIXES, fill
from build_sitemap import public_urls, validate_last_updated, verification_files
from http_client import fetch_url
from llms_txt import _local_path, has_link_relation, markdown_alternate, validate_llms_txt
from email_addresses import address_key, contact_values, validate_email_address

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parser = argparse.ArgumentParser(description='Check a built static site against its public configuration.')
parser.add_argument('--site', default=os.path.join(REPO, 'site'), help='built directory to inspect')
parser.add_argument('--config', default=os.path.join(REPO, 'site.config.json'), help='matching public configuration')
parser.add_argument('--live', action='store_true', help='also request the configured public HTTPS site')
parser.add_argument('--rules', help='private gate rules (default: quality.local.json in the repository, '
                                    'optional and ignored by Git; see quality.local.example.json)')
args = parser.parse_args()
R = os.path.abspath(args.site)
_cfg_path = os.path.abspath(args.config)
_rules_path = os.path.abspath(args.rules) if args.rules else os.path.join(REPO, 'quality.local.json')


def load_gate_config(path):
    """Return the public config, or one reason the gate cannot check against it.

    Every rule compares the build with this file. Checking against a guessed
    domain instead reports a page of failures that never name the real cause.
    Only DOMAIN is required here; the builder validates the rest.
    """
    name = os.path.basename(path)
    if not os.path.isfile(path):
        return None, "%s not found; create it with: python scripts/fork.py --init" % name
    try:
        with open(path, encoding="utf-8") as config_file:
            cfg = json.load(config_file)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, "%s is not valid JSON: %s" % (name, exc)
    except OSError as exc:
        return None, "%s could not be read: %s" % (name, exc)
    if not isinstance(cfg, dict):
        return None, "%s must contain a JSON object" % name
    if not isinstance(cfg.get("DOMAIN"), str) or not cfg["DOMAIN"].strip():
        return None, "%s must set DOMAIN to a nonempty string" % name
    try:
        verification_files(cfg)
    except ValueError as exc:
        return None, "%s: %s" % (name, exc)
    return cfg, None


def load_rules(path, required):
    """Return (forbidden, allowed, style) from the private rules file, or a problem.

    The file stays out of Git so a public fork never publishes its forbidden
    strings. A problem message names the field, never an entry's text.
    """
    style = {"em_dash": True, "american_spelling": True}
    name = os.path.basename(path)
    if not os.path.isfile(path):
        if required:
            return None, "rules file %s not found" % path
        return ([], [], style), None
    try:
        with open(path, encoding="utf-8") as rules_file:
            data = json.load(rules_file)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, "%s is not valid JSON: %s" % (name, exc)
    except OSError as exc:
        return None, "%s could not be read: %s" % (name, exc)
    if not isinstance(data, dict):
        return None, "%s must contain a JSON object" % name
    unknown = sorted(key for key in data if not key.startswith("_")
                     and key not in {"forbidden", "allowed", "style"})
    if unknown:
        return None, "%s has unknown keys: %s" % (name, ", ".join(unknown))
    forbidden = data.get("forbidden", [])
    if not isinstance(forbidden, list):
        return None, "%s: forbidden must be a list of strings" % name
    for index, entry in enumerate(forbidden, 1):
        if not isinstance(entry, str) or not entry.strip():
            return None, "%s: forbidden string #%d must be a nonempty string" % (name, index)
    allowed = data.get("allowed", [])
    if not isinstance(allowed, list):
        return None, "%s: allowed must be a list of objects" % name
    compiled = []
    for index, entry in enumerate(allowed, 1):
        if not isinstance(entry, dict) or set(entry) - {"pattern", "reason"}:
            return None, "%s: allowed entry #%d must have only pattern and reason" % (name, index)
        if not isinstance(entry.get("pattern"), str) or not entry["pattern"]:
            return None, "%s: allowed entry #%d needs a nonempty pattern" % (name, index)
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            return None, "%s: allowed entry #%d needs a nonempty reason" % (name, index)
        try:
            compiled.append((re.compile(entry["pattern"]), entry["reason"]))
        except re.error as exc:
            return None, "%s: allowed entry #%d pattern is not a valid regular expression: %s" % (name, index, exc)
    switches = data.get("style", {})
    if not isinstance(switches, dict) or set(switches) - set(style):
        return None, "%s: style may set only em_dash and american_spelling" % name
    for key, value in switches.items():
        if not isinstance(value, bool):
            return None, "%s: style.%s must be true or false" % (name, key)
        style[key] = value
    return (forbidden, compiled, style), None


_cfg, _cfg_problem = load_gate_config(_cfg_path)
if _cfg_problem:
    print("FAIL %s" % _cfg_problem)
    sys.exit(1)
_rules, _rules_problem = load_rules(_rules_path, required=bool(args.rules))
if _rules_problem:
    print("FAIL %s" % _rules_problem)
    sys.exit(1)
# Strings that must never appear anywhere in the build, deliberate exceptions
# with their reasons, and the two writing-style switches.
FORBIDDEN, ALLOWED, STYLE = _rules
if not os.path.isdir(R):
    parser.error('--site must name an existing built directory')
DOMAIN = _cfg["DOMAIN"]
EMAIL = _cfg.get("EMAIL", "")
JOB_TITLE = _cfg.get("JOB_TITLE", "")
LIVE = args.live
# Search-engine proofs the builder writes at the root. They are not pages, so
# the page rules and the sitemap leave them out.
VERIFICATION_FILES = verification_files(_cfg)
# llms-full.txt is generated by concatenation: any violation in it mirrors a
# source file and would be double-counted, so it is scanned separately at the end.
GENERATED = {"llms-full.txt"}

fails, warns = [], []

def sources(include_generated=False):
    """Return the published pages every rule scans, at any depth.

    Root files keep the wider .md/.txt/.html/.xml scope; pages below the root
    are .md and .html. Walking the whole build means a nested page that a
    generator skipped still reaches the byte and rule checks. Dot-directories
    such as .well-known hold machine files with their own checks.
    """
    out = []
    for dirpath, dirnames, filenames in os.walk(R):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        top = dirpath == R
        suffixes = (".md", ".txt", ".html", ".xml") if top else (".md", ".html")
        for f in sorted(filenames):
            if not f.endswith(suffixes):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), R).replace(os.sep, "/")
            if top and f in GENERATED and not include_generated:
                continue
            if top and f in VERIFICATION_FILES:
                continue
            out.append((rel, os.path.join(dirpath, f)))
    return out

def read(p):
    with open(p, encoding="utf-8", errors="ignore") as source:
        return source.read()

def fetch_live(path):
    """Return status, headers, body, and any transport error for a live path."""
    return fetch_url("https://" + DOMAIN + path)

def header_values(headers, name):
    """Return every value sent for one header, however the client stored them."""
    if hasattr(headers, "get_all"):
        return list(headers.get_all(name) or [])
    value = headers.get(name)
    return [] if value is None else [value]

ATOM = "{http://www.w3.org/2005/Atom}"
ATOM_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

def _schema_org(value):
    """Return whether a JSON-LD @context names schema.org in any legal form."""
    if isinstance(value, str):
        return value.rstrip("/") == "https://schema.org"
    if isinstance(value, list):
        return any(_schema_org(item) for item in value)
    if isinstance(value, dict):
        return any(_schema_org(item) for item in value.values())
    return False

def structured_data_issues(document, label):
    """Return defects that stop a consumer before it reads the declared facts.

    Cross-document @id references stay legal: an Article may name the
    homepage's #person. What cannot be right is a document that declares no
    schema.org context, a node with no @type, or one @id declared twice.
    """
    issues = []
    if not _schema_org(document.get("@context")):
        issues.append("%s does not declare the schema.org context" % label)
    nodes = document.get("@graph")
    nodes = nodes if isinstance(nodes, list) else [document]
    identifiers = []
    for node in nodes:
        if not isinstance(node, dict):
            issues.append("%s has a JSON-LD node that is not an object" % label)
            continue
        if not isinstance(node.get("@type"), str) or not node["@type"].strip():
            issues.append("%s has a JSON-LD node with no @type" % label)
        if isinstance(node.get("@id"), str) and node["@id"].strip():
            identifiers.append(node["@id"])
    duplicates = sorted({value for value in identifiers if identifiers.count(value) > 1})
    issues.extend("%s declares @id %s more than once" % (label, value) for value in duplicates)
    return issues

def feed_issues(root, domain):
    """Return violations of the Atom structure docs/WRITING.md promises.

    A feed reader that cannot resolve an entry, or that is handed a date the
    build never validated, silently drops articles. Nothing checked either.
    """
    try:
        feed = ET.parse(os.path.join(root, "feed.xml")).getroot()
    except (ET.ParseError, OSError) as exc:
        return ["feed.xml is missing or invalid: %s" % exc]
    if feed.tag != ATOM + "feed":
        return ["feed.xml must be a single Atom feed element"]
    issues = []
    for field in ("id", "title", "updated"):
        if feed.findtext(ATOM + field, "").strip() == "":
            issues.append("feed.xml has no <%s>" % field)
    stamps = [("", feed.findtext(ATOM + "updated", "").strip())]
    seen_ids = []
    for entry in feed.findall(ATOM + "entry"):
        label = entry.findtext(ATOM + "id", "").strip() or "<entry without an id>"
        if label != "<entry without an id>":
            if label in seen_ids:
                issues.append("feed.xml repeats entry id %s" % label)
            seen_ids.append(label)
        for field in ("id", "title", "updated"):
            if entry.findtext(ATOM + field, "").strip() == "":
                issues.append("feed.xml entry %s has no <%s>" % (label, field))
        stamps.append((label, entry.findtext(ATOM + "updated", "").strip()))
        entry_link = entry.find(ATOM + "link")
        href = entry_link.get("href", "") if entry_link is not None else ""
        try:
            target = urlsplit(href)
            port = target.port
        except ValueError:
            target, port = None, None
        if target is None or target.hostname is None or target.hostname.lower() != domain.lower():
            issues.append("feed.xml entry %s does not link to the configured site" % label)
        elif target.scheme.lower() != "https" or port not in (None, 443) or target.username or target.password:
            issues.append("feed.xml entry %s does not use the canonical HTTPS origin" % label)
        else:
            # Same hole as the search index: writing/../profile.html is a real
            # file once the kernel resolves "..".
            local = _local_path(href, domain, root)
            if local == "invalid":
                issues.append("feed.xml entry %s has an invalid same-site path" % label)
            elif local is None or not local.is_file():
                issues.append("feed.xml entry %s links to a missing build artifact %s" % (label, target.path))
    self_link = [link for link in feed.findall(ATOM + "link")
                 if "self" in link.get("rel", "").split()]
    if len(self_link) != 1 or self_link[0].get("href", "") != "https://%s/feed.xml" % domain:
        issues.append("feed.xml must declare one rel=self link to https://%s/feed.xml" % domain)
    for label, stamp in stamps:
        if not stamp:
            continue
        if not ATOM_STAMP.fullmatch(stamp):
            issues.append("%s <updated> %r is not an RFC 3339 UTC timestamp" % (label or "feed.xml", stamp))
            continue
        hour, minute, second = (int(part) for part in stamp[11:19].split(":"))
        # 60 is the leap second RFC 3339 allows. 99:99:99 matches the digit
        # pattern and is not a time.
        if hour > 23 or minute > 59 or second > 60:
            issues.append("%s <updated> %r is not an RFC 3339 UTC timestamp" % (label or "feed.xml", stamp))
            continue
        try:
            validate_last_updated(stamp[:10])
        except ValueError:
            issues.append("%s <updated> %r is not a calendar date" % (label or "feed.xml", stamp))
    return issues

class _JsonLd(HTMLParser):
    """Collect every JSON-LD script, not only one exact tag spelling."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.blocks = []
        self._buffer = None

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        media = values.get("type", "").split(";", 1)[0].strip().lower()
        if media == "application/ld+json":
            self._buffer = []

    def handle_data(self, data):
        if self._buffer is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._buffer is not None:
            self.blocks.append("".join(self._buffer))
            self._buffer = None


def json_ld_blocks(document):
    """Return JSON-LD bodies, including tags with parameters or other attributes.

    A regex for `<script type="application/ld+json">` skips a charset parameter
    or an id, so a block that does not parse never reaches the gate.
    """
    parser = _JsonLd()
    parser.feed(document)
    parser.close()
    return parser.blocks


def head(msg):
    print("\n" + "=" * 68 + "\n" + msg + "\n" + "=" * 68)

def search_index_issues(root):
    """Return violations of the search index and its static directory contract.

    docs/WRITING.md promises that /search.md still lists every indexed page
    when a browser cannot load search-index.json. Nothing enforced that, so a
    stale record could send a reader to a page the build no longer publishes.
    """
    try:
        with open(os.path.join(root, "search-index.json"), encoding="utf-8") as source:
            records = json.load(source)
    except (OSError, ValueError) as exc:
        return ["search-index.json is missing or invalid: %s" % exc]
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        return ["search-index.json must be a list of records"]
    issues, urls = [], []
    for record in records:
        url = record.get("url")
        parsed = urlsplit(url) if isinstance(url, str) else None
        if not parsed or not url.startswith("/") or parsed.query or parsed.fragment:
            issues.append("search-index.json record has an unusable url: %r" % (url,))
            continue
        if url in urls:
            issues.append("search-index.json repeats url %s" % url)
            continue
        urls.append(url)
        # os.path.join("site", "writing/../profile.html") is the profile page,
        # so a lexical ".." still looks like a published file. Reject it before
        # the filesystem resolves the path.
        local = _local_path("https://local.invalid" + url, "local.invalid", root)
        if local == "invalid":
            issues.append("search-index.json url escapes the build: %s" % url)
        elif local is None or not local.is_file():
            issues.append("search-index.json links to a missing build artifact %s" % url)
    directory = os.path.join(root, "search.md")
    if not os.path.isfile(directory):
        return issues + ["search.md is missing from the build"]
    listed = re.findall(r"^- \[[^\]]*\]\((\S+)\)\s*$", read(directory), re.M)
    if sorted(listed) != sorted(urls):
        issues.append("search.md and search-index.json disagree about %s"
                      % sorted(set(listed) ^ set(urls)))
    return issues

def url_spans(text):
    """URLs are identifiers, not prose. Spelling rules do not apply inside them."""
    return [(m.start(), m.end()) for m in re.finditer(r"https?://[^\s)\"'<>\]]+", text)]

def allowed_at(text, pos, spans=None):
    """Return whether a match at pos is exempt: inside a URL or an allowed window.

    Pass spans=[] to keep only the allowed-pattern exemption.
    """
    if spans is None:
        spans = url_spans(text)
    for a, b in spans:
        if a <= pos < b:
            return True
    for pattern, _ in ALLOWED:
        for m in pattern.finditer(text):
            if m.start() - 120 <= pos <= m.end() + 120:
                return True
    return False

def build_files():
    """Return (relative path, path, is binary) for every file in the build.

    Dot-directories are included: .well-known/agent-card.json comes from a
    user file, and search-index.json or the manifest can carry any page text.
    """
    out = []
    for dirpath, dirnames, filenames in os.walk(R):
        dirnames.sort()
        for f in sorted(filenames):
            path = os.path.join(dirpath, f)
            out.append((os.path.relpath(path, R).replace(os.sep, "/"), path,
                        f.lower().endswith(BINARY_SUFFIXES)))
    return out

head("1. RULE COMPLIANCE")
# Forbidden strings are a fork's most sensitive entries, so they are matched
# literally, never inside a regex, and a hit names only the entry's number and
# the file. Echoing the matched text would publish it in CI logs.
forbidden_patterns = [re.compile(re.escape(entry), re.IGNORECASE) for entry in FORBIDDEN]

def shown_path(rel):
    """A path that itself contains a forbidden string is not printed either."""
    return "a withheld path" if any(p.search(rel) for p in forbidden_patterns) else rel

forbidden_hits = Counter()
for index, pattern in enumerate(forbidden_patterns, 1):
    for rel, p, binary in build_files():
        if pattern.search(rel):
            forbidden_hits[(index, "the file name of " + shown_path(rel))] += 1
        if binary:
            continue
        t = read(p)
        for m in pattern.finditer(t):
            if not allowed_at(t, m.start(), spans=[]):
                forbidden_hits[(index, shown_path(rel))] += 1
if forbidden_hits:
    total = sum(forbidden_hits.values())
    named = ["forbidden string #%d in %s (%d)" % (index, rel, count)
             for (index, rel), count in sorted(forbidden_hits.items())]
    fails.append("forbidden strings (%d)" % total)
    more = " and %d more file locations" % (len(named) - 8) if len(named) > 8 else ""
    print("  FAIL %-28s %d  %s%s" % ("forbidden strings", total, named[:8], more))
else:
    print("  ok   %-28s 0  (%d configured)" % ("forbidden strings", len(FORBIDDEN)))

RULES = []
if STYLE["em_dash"]:
    RULES.append(("em/en dash", r"[–—]|&mdash;|&ndash;"))
if STYLE["american_spelling"]:
    # Only words where American English genuinely differs. A blanket [a-z]+ised
    # is wrong: revise, advise, promise, comprise and friends are -ise in BOTH
    # dialects, and an earlier version flagged "revised" as a British spelling.
    RULES.append(("British spelling", r"(?i)\b(licence|behaviour|colour|favour|centre|defence|offence|"
                                      r"programme|modelled|modelling|labelled|cancelled|travelled|"
                                      r"analyse|analysed|organis(e|ed|ing|ation)|optimis(e|ed|ing|ation)|"
                                      r"realis(e|ed|ing)|recognis(e|ed|ing)|prioritis(e|ed|ing)|"
                                      r"standardis(e|ed|ing|ation)|summaris(e|ed|ing)|specialis(e|ed)|"
                                      r"minimis(e|ed)|maximis(e|ed)|utilis(e|ed)|capitalis(e|ed)|"
                                      r"tokenis(e|ed|ation)|monetis(e|ed)|centralis(e|ed)|"
                                      r"decentralis(e|ed)|collateralis(e|ed)|normalis(e|ed))\b"))
for name, pat in RULES:
    hits = []
    for rel, p in sources():
        t = read(p)
        for m in re.finditer(pat, t):
            if allowed_at(t, m.start()):
                continue
            hits.append("%s:%s" % (rel, m.group(0)))
    if hits:
        fails.append("%s (%d)" % (name, len(hits)))
        print("  FAIL %-28s %d  %s" % (name, len(hits), hits[:4]))
    else:
        print("  ok   %-28s 0" % name)
for name, key in (("em/en dash", "em_dash"), ("British spelling", "american_spelling")):
    if not STYLE[key]:
        print("  off  %-28s style.%s is false in the rules file" % (name, key))

head("2. CROSS-FILE FACT CONSISTENCY")
FACTS = [
    ("job title", r"(?i)\b(%s)\b" % re.escape(JOB_TITLE) if JOB_TITLE else r"(?!x)x", {JOB_TITLE.lower()}),
]
for name, pat, allowed in FACTS:
    found = {}
    for rel, p in sources():
        for m in re.finditer(pat, read(p)):
            v = m.group(1) if m.groups() else m.group(0)
            found.setdefault(v, []).append(rel)
    # compare case-insensitively: a title is the same title in any casing
    allowed = {a.lower() for a in allowed if a}
    bad = {k: v[:2] for k, v in found.items() if k.lower() not in allowed}
    if bad:
        fails.append("%s: %s" % (name, list(bad)))
        print("  FAIL %-18s unexpected: %s" % (name, bad))
    else:
        print("  ok   %-18s %s" % (name, sorted(found)))

if EMAIL:
    try:
        validate_email_address(EMAIL)
        expected_email = address_key(EMAIL)
    except ValueError as exc:
        expected_email = None
        fails.append(str(exc))
    found, bad = {}, {}
    domains = {DOMAIN.lower(), EMAIL.rsplit("@", 1)[-1].lower()}
    for rel, path in sources():
        prose, routes = contact_values(read(path), os.path.splitext(rel)[1].lower())
        candidates = routes + [value for value in prose if value.rsplit("@", 1)[-1].lower() in domains]
        for value in candidates:
            found.setdefault(value, []).append(rel)
            try:
                validate_email_address(value)
                consistent = address_key(value) == expected_email
            except ValueError:
                consistent = False
            if not consistent:
                bad.setdefault(value, []).append(rel)
    if bad:
        fails.append("email: %s" % list(bad))
        print("  FAIL email unexpected: %s" % bad)
    else:
        print("  ok   email %s" % sorted(found))

head("3. PAGE HEAD METADATA")
class _Head(HTMLParser):
    """Collect the head facts every indexable page has to declare."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.description = None
        self.robots = None
        self.canonicals = []
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "html":
            self.lang = values.get("lang", "").strip() or None
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            name = (values.get("name") or values.get("property") or "").lower()
            if name == "description" and self.description is None:
                self.description = values.get("content", "").strip() or None
            elif name == "robots" and self.robots is None:
                self.robots = values.get("content", "").strip() or None
        elif tag == "link" and "canonical" in values.get("rel", "").lower().split():
            href = values.get("href", "").strip()
            if href:
                self.canonicals.append(href)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False


for rel, p in sources():
    if not rel.endswith(".html"):
        continue
    head_facts = _Head()
    head_facts.feed(read(p))
    head_facts.close()
    head_facts.title = head_facts.title.strip()
    problems = []
    if not head_facts.lang:
        problems.append("%s has no non-empty <html lang>" % rel)
    if not head_facts.title:
        problems.append("%s has no non-empty <title>" % rel)
    # A page marked noindex is not an indexable result, so a description would
    # never be shown. Only indexable pages are required to carry one.
    indexed = "noindex" not in (head_facts.robots or "").lower()
    if indexed and not head_facts.description:
        problems.append("%s has no non-empty <meta name=description>" % rel)
    # index.html is served at /. Any other non-empty href, including another
    # host or a root-relative path, tells a crawler this page lives elsewhere.
    expected_canonical = "https://%s/" % DOMAIN if rel == "index.html" else (
        "https://%s/%s" % (DOMAIN, quote(rel, safe="/-._~"))
    )
    if indexed and head_facts.canonicals != [expected_canonical]:
        if not head_facts.canonicals:
            problems.append("%s has no <link rel=canonical>" % rel)
        else:
            problems.append("%s canonical is not %s" % (rel, expected_canonical))
    for problem in problems:
        fails.append(problem)
        print("  FAIL %s" % problem)
    if not problems:
        print("  ok   %-40s lang=%s desc=%s canonical=%s"
              % (rel, head_facts.lang, "yes" if head_facts.description else "noindex",
                 head_facts.canonicals[0] if head_facts.canonicals else "none"))

head("4. STRUCTURED DATA")
for rel, p in sources():
    if not rel.endswith(".html") or rel == "404.html":
        continue
    for block in json_ld_blocks(read(p)):
        try:
            d = json.loads(block)
            issues = (structured_data_issues(d, rel) if isinstance(d, dict)
                      else ["%s JSON-LD is not an object" % rel])
            for issue in issues:
                fails.append(issue)
                print("  FAIL %s" % issue)
            if isinstance(d, dict) and "@graph" in d:
                if not issues:
                    print("  ok   %-40s %s" % (rel, [n.get("@type") for n in d["@graph"]]))
            else:
                linked = d.get("author", {}).get("@id") == "" + "https://" + DOMAIN + "/#person"
                print("  %-4s %-40s %s author->#person" % ("ok" if linked else "FAIL", rel, d.get("@type")))
                if not linked:
                    fails.append("%s author not linked to #person" % rel)
        except Exception as e:
            fails.append("%s JSON-LD invalid" % rel)
            print("  FAIL %-40s %s" % (rel, e))

head("5. LLMS.TXT V2")
llms_path = os.path.join(R, "llms.txt")
if not os.path.isfile(llms_path):
    fails.append("llms.txt is missing")
    print("  FAIL llms.txt is missing")
else:
    llms_issues = validate_llms_txt(read(llms_path), DOMAIN, R)
    if llms_issues:
        for issue in llms_issues:
            fails.append("llms.txt: %s" % issue)
            print("  FAIL %s" % issue)
    else:
        print("  ok   llms.txt follows the v2 file-list contract")

for rel, p in sources():
    if not rel.endswith(".html") or rel == "404.html":
        continue
    document = read(p)
    if not has_link_relation(document, "describedby", "/llms.txt"):
        fails.append("%s does not advertise /llms.txt" % rel)
        print("  FAIL %-40s missing rel=describedby" % rel)
    else:
        print("  ok   %-40s advertises /llms.txt" % rel)
    markdown = markdown_alternate(rel)
    if not has_link_relation(document, "alternate", markdown, "text/markdown"):
        fails.append("%s does not advertise %s" % (rel, markdown))
        print("  FAIL %-40s missing Markdown alternate" % rel)

head("6. OPTIONAL A2A V1 AGENT CARD")
card_path = os.path.join(R, ".well-known", "agent-card.json")
if not os.path.exists(card_path):
    print("  ok   disabled; no Agent Card is published for this static site")
else:
    try:
        agent_card = load_agent_card(card_path)
        card_issues = validate_agent_card(agent_card)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        agent_card = None
        card_issues = [str(exc)]
    if card_issues:
        for issue in card_issues:
            fails.append("A2A Agent Card: %s" % issue)
            print("  FAIL %s" % issue)
    else:
        print("  ok   /.well-known/agent-card.json has a valid public A2A v1 structure")
        if agent_card.get("signatures"):
            print("  note signature fields are present; cryptographic verification is external")

head("7. LAST-UPDATED DATES")
configured_lastmod = _cfg.get("LAST_UPDATED")
try:
    expected_lastmod = validate_last_updated(configured_lastmod)
    print("  ok   site.config.json LAST_UPDATED is %s" % expected_lastmod)
except ValueError as exc:
    expected_lastmod = None
    fails.append(str(exc))
    print("  FAIL %s" % exc)
for rel, p in sources():
    if not rel.endswith(".md"):
        continue
    match = re.search(r"Last updated:\s*(\S+)", read(p))
    if not match:
        warns.append("%s has no 'Last updated'" % rel)
        print("  WARN %-40s no Last updated line" % rel)
        continue
    page_lastmod = match.group(1).rstrip(".,;:)")
    try:
        validate_last_updated(page_lastmod)
    except ValueError:
        fails.append("%s has an invalid Last updated date" % rel)
        print("  FAIL %-40s invalid Last updated date" % rel)
print("  (files with a date are not listed)")

def source_sections(bundle):
    """Map each llms-full.txt SOURCE URL to the bytes published under it.

    The separator before the next header is two newlines added by the builder,
    not part of the page. A page whose text merely occurs inside another page
    has no section of its own.
    """
    header = re.compile(r"={70}\n# SOURCE: (\S+)\n={70}\n\n")
    matches = list(header.finditer(bundle))
    sections = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(bundle)
        if index + 1 < len(matches) and bundle[end - 2:end] == "\n\n":
            end -= 2
        sections.setdefault(match.group(1), []).append(bundle[start:end])
    return sections


head("8. GENERATED FILE IS IN SYNC")
lf = os.path.join(R, "llms-full.txt")
if os.path.exists(lf):
    t = read(lf)
    # build.py publishes a plain-text spelling of the configured address when
    # the HTML spelling would break Markdown, so accept either spelling of
    # that one token and nothing else. Derive both with the builder's own rule.
    escaped = fill("{{EMAIL}}", _cfg, plain_text=False)
    plain = fill("{{EMAIL}}", _cfg, plain_text=True)
    sections = source_sections(t)
    missing = []
    for rel, p in sources():
        if not rel.endswith(".md") or rel in ("404.md",):
            continue
        text = read(p)
        acceptable = {text}
        if escaped and escaped != plain:
            acceptable.add(text.replace(escaped, plain))
        url = "https://%s/%s" % (DOMAIN, quote(rel, safe="/-._~"))
        bodies = sections.get(url, [])
        if len(bodies) != 1 or bodies[0] not in acceptable:
            missing.append(rel)
    if missing:
        fails.append("llms-full.txt does not contain the current bytes of: %s" % missing)
        print("  FAIL llms-full.txt is stale, missing current bytes for: %s" % missing)
    else:
        print("  ok   llms-full.txt contains the current bytes of every .md source")

index_issues = search_index_issues(R)
for issue in index_issues:
    fails.append(issue)
    print("  FAIL %s" % issue)
if not index_issues:
    print("  ok   search-index.json and search.md describe the same built pages")

feed_problems = feed_issues(R, DOMAIN)
for issue in feed_problems:
    fails.append("feed.xml: %s" % issue)
    print("  FAIL feed.xml %s" % issue)
if not feed_problems:
    print("  ok   feed.xml is a valid Atom feed for %s" % DOMAIN)

head("9. SITEMAP MATCHES BUILD OUTPUT")
sitemap_path = os.path.join(R, "sitemap.xml")
try:
    root = ET.parse(sitemap_path).getroot()
    entries = root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")
    actual_urls = [entry.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc", "") for entry in entries]
    expected_urls = public_urls(R, DOMAIN, VERIFICATION_FILES)
    duplicates = sorted(url for url, count in Counter(actual_urls).items() if count > 1)
    missing = sorted(set(expected_urls) - set(actual_urls))
    stale = sorted(set(actual_urls) - set(expected_urls))
    lastmods = [entry.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod", "") for entry in entries]
    malformed_lastmod = [
        url for url, value in zip(actual_urls, lastmods)
        if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
    ]
    for url, value in zip(actual_urls, lastmods):
        if not value or url in malformed_lastmod:
            continue
        try:
            validate_last_updated(value)
        except ValueError:
            malformed_lastmod.append(url)
    bad_lastmod = [
        url for url, value in zip(actual_urls, lastmods) if value != expected_lastmod
    ] if expected_lastmod is not None else []
    unexpected_lastmod = [
        url for url, value in zip(actual_urls, lastmods) if value
    ] if expected_lastmod is None else []
    if duplicates:
        fails.append("sitemap.xml has duplicate URLs: %s" % duplicates)
        print("  FAIL duplicate URLs: %s" % duplicates)
    if missing:
        fails.append("sitemap.xml missing built files: %s" % missing)
        print("  FAIL missing built files: %s" % missing)
    if stale:
        fails.append("sitemap.xml has URLs without built files: %s" % stale)
        print("  FAIL URLs without built files: %s" % stale)
    if malformed_lastmod:
        malformed_lastmod = sorted(set(malformed_lastmod))
        fails.append("sitemap.xml has malformed lastmod dates: %s" % malformed_lastmod)
        print("  FAIL malformed lastmod dates: %s" % malformed_lastmod)
    if bad_lastmod:
        fails.append("sitemap.xml lastmod does not match LAST_UPDATED: %s" % bad_lastmod)
        print("  FAIL lastmod differs from LAST_UPDATED: %s" % bad_lastmod)
    if unexpected_lastmod:
        fails.append("sitemap.xml has lastmod dates without a valid LAST_UPDATED: %s" % unexpected_lastmod)
        print("  FAIL unexpected lastmod without valid LAST_UPDATED: %s" % unexpected_lastmod)
    if not duplicates and not missing and not stale and not malformed_lastmod and not bad_lastmod and not unexpected_lastmod:
        print("  ok   %d sitemap URLs match public build artifacts" % len(actual_urls))
        if expected_lastmod is not None:
            print("  ok   every lastmod matches LAST_UPDATED (%s)" % expected_lastmod)
except (ET.ParseError, OSError) as exc:
    fails.append("sitemap.xml is missing or invalid: %s" % exc)
    print("  FAIL sitemap.xml is missing or invalid: %s" % exc)

robots_path = os.path.join(R, "robots.txt")
if not os.path.isfile(robots_path):
    fails.append("robots.txt is missing from the build")
    print("  FAIL robots.txt is missing from the build")
else:
    lines = [line.strip() for line in read(robots_path).splitlines()]
    declared = [line[len("Sitemap:"):].strip() for line in lines
                if line.casefold().startswith("sitemap:")]
    expected_sitemap = "https://%s/sitemap.xml" % DOMAIN
    if not declared:
        fails.append("robots.txt declares no Sitemap")
        print("  FAIL robots.txt declares no Sitemap")
    for value in declared:
        if value != expected_sitemap:
            fails.append("robots.txt Sitemap is %s, not %s" % (value, expected_sitemap))
            print("  FAIL robots.txt Sitemap is %s, not %s" % (value, expected_sitemap))
    # A bare Disallow: / for unspecified agents contradicts the file's own
    # header, which states the site is meant to be crawled and cited.
    # Consecutive User-agent lines are one group. Remembering only the latest
    # agent misses Disallow: / when * is listed beside another crawler.
    # The colon may have no space after it: Disallow:/ is the same rule.
    catch_all_blocked = False
    agents, started_rules = [], False
    for line in lines:
        if not line or line.startswith("#"):
            if not line:
                agents, started_rules = [], False
            continue
        if line.casefold().startswith("user-agent:"):
            if started_rules:
                agents, started_rules = [], False
            agents.append(line.split(":", 1)[1].strip())
            continue
        started_rules = True
        directive, _, value = line.partition(":")
        if directive.casefold() == "disallow" and value.strip() == "/" and "*" in agents:
            catch_all_blocked = True
    if catch_all_blocked:
        fails.append("robots.txt blocks every unspecified crawler with 'Disallow: /'")
        print("  FAIL robots.txt blocks every unspecified crawler with 'Disallow: /'")
    if declared == [expected_sitemap] and not catch_all_blocked:
        print("  ok   robots.txt points crawlers at %s" % expected_sitemap)

if LIVE:
    head("10. LIVE: LINKS AND SITEMAP")
    links = set()
    for rel, p in sources():
        for m in re.finditer(r"https://" + re.escape(DOMAIN) + r"(/[^\s)\"'<>\]]*)?", read(p)):
            # ! and ? end a sentence the same way the Markdown autolinker does.
            # Leaving them on the path makes --live request a file that was never built.
            u = (m.group(1) or "/").rstrip(".,;:!?")
            links.add(u)
    sm = read(os.path.join(R, "sitemap.xml"))
    links |= set(re.findall(r"<loc>https://" + re.escape(DOMAIN) + r"(/[^<]*)</loc>", sm))
    print("  checking %d distinct URLs..." % len(links))
    bad = []
    for u in sorted(links):
        status, _, _, error = fetch_live(u)
        if status != 200:
            bad.append((u, str(status) if status else error or "no status"))
    for u, c in bad:
        fails.append("link %s -> %s" % (u, c))
        print("  FAIL %-50s %s" % (u, c))
    if not bad:
        print("  ok   every URL resolves 200")

    # ownership proofs: deleting any of these un-verifies the site
    print("\n  ownership proofs:")
    verification = _cfg.get("verification", {}) if isinstance(_cfg.get("verification", {}), dict) else {}
    domain = _cfg.get("DOMAIN", "")
    ownership_targets: list[str] = []
    google_file = verification.get("google_html_file") or ""
    if google_file:
        ownership_targets.append(f"https://{domain}/{google_file}")
    indexnow_key = verification.get("indexnow_key") or ""
    if indexnow_key:
        ownership_targets.append(f"https://{domain}/{indexnow_key}.txt")
    for u in ownership_targets:
        status, _, _, _ = fetch_live(u)
        ok = status == 200
        if not ok:
            fails.append("ownership proof missing: %s" % u)
        print("    %-4s %s" % ("ok" if ok else "FAIL", u))

    # The shipped host configs send these on every response. A deployment made
    # before they were added still serves correct facts, so a missing header
    # warns instead of failing until the next redeploy picks it up.
    status, headers, _, _ = fetch_live("/")
    if status == 200:
        nosniff = [value.strip().lower() for value in header_values(headers, "X-Content-Type-Options")] == ["nosniff"]
        csp = any(value.strip() for value in header_values(headers, "Content-Security-Policy"))
        for present, label in ((nosniff, "X-Content-Type-Options: nosniff"),
                               (csp, "Content-Security-Policy")):
            if not present:
                warns.append("live homepage is served without %s" % label)
            print("\n  %-4s homepage sends %s" % ("ok" if present else "WARN", label))

    # markdown must render inline, not download
    status, headers, _, _ = fetch_live("/profile.md")
    content_type = headers.get("Content-Type", "").lower()
    disposition = headers.get("Content-Disposition", "").lower()
    inline = status == 200 and "text/markdown" in content_type and "inline" in disposition
    if not inline:
        fails.append("profile.md not served inline: .htaccess may not be applying (check chmod 644)")
    print("\n  %-4s markdown served inline as text/markdown" % ("ok" if inline else "FAIL"))

    if os.path.exists(card_path):
        status, headers, remote_bytes, _ = fetch_live("/.well-known/agent-card.json")
        status_ok = status == 200
        content_type_ok = (
            headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            == "application/a2a+json"
        )
        cache_ok = bool(re.search(r"\bmax-age=\d+", headers.get("Cache-Control", ""), re.IGNORECASE))
        etag_ok = bool(headers.get("ETag"))
        # Browsers reject a repeated or comma-joined value such as "*, *",
        # which a host emits when two matching rules both set the header.
        cors_ok = [value.strip() for value in header_values(headers, "Access-Control-Allow-Origin")] == ["*"]
        card_live = status_ok and content_type_ok
        if not card_live:
            fails.append("live Agent Card is missing or has the wrong content type")
        if not cache_ok:
            fails.append("live Agent Card has no Cache-Control max-age")
        if status_ok and not cors_ok:
            fails.append("live Agent Card Access-Control-Allow-Origin is not exactly *")
        if not etag_ok:
            warns.append("live Agent Card has no ETag for conditional requests")
        print("  %-4s A2A Agent Card served as application/a2a+json" % ("ok" if card_live else "FAIL"))
        print("  %-4s A2A Agent Card has Cache-Control max-age" % ("ok" if cache_ok else "FAIL"))
        if status_ok:
            print("  %-4s A2A Agent Card sends Access-Control-Allow-Origin: *" % ("ok" if cors_ok else "FAIL"))
        print("  %-4s A2A Agent Card has an ETag" % ("ok" if etag_ok else "WARN"))
        if status_ok:
            with open(card_path, "rb") as local_card:
                current_bytes = remote_bytes == local_card.read()
            if not current_bytes:
                fails.append("live Agent Card bytes differ from the validated local build")
            print("  %-4s live Agent Card matches validated local bytes" % ("ok" if current_bytes else "FAIL"))
    else:
        remote_status, _, _, remote_error = fetch_live("/.well-known/agent-card.json")
        card_absent = remote_status in {404, 410}
        if not card_absent:
            fails.append(
                "A2A is disabled locally but the live Agent Card path returned %s"
                % (remote_status or remote_error or "no status")
            )
        print(
            "  %-4s A2A disabled and live discovery is absent (404 or 410)"
            % ("ok" if card_absent else "FAIL")
        )

head("SUMMARY")
print("  FAILURES: %d" % len(fails))
for f in fails:
    print("    - %s" % f)
print("  WARNINGS: %d" % len(warns))
for w in warns:
    print("    - %s" % w)
sys.exit(1 if fails else 0)

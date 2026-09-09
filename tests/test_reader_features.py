import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build import validate_public_contacts, validate_email_address, json_block
from build_writing_html import render_page, md_to_html
from build_catalog import run as build_catalog
from build_inventory import run as build_inventory, inventory
from build import build_site_staged, paths_overlap
import ntpath
from unittest.mock import patch
from check_artifacts import audit, Document
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

CFG = {"DOMAIN": "example.test", "FULL_NAME": "Example Person", "EMAIL": "person@example.test",
       "EMPLOYER_URL": "https://example.test", "LINKEDIN_SLUG": "example-person",
       "X_HANDLE": "example_person", "LAST_UPDATED": "2026-01-01", "JOB_TITLE": "Writer"}


class TextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text, self.tags = [], []
    def handle_data(self, value):
        self.text.append(value)
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


class ReaderFeatures(unittest.TestCase):
    def test_root_search_titles_come_from_first_rendered_h1(self):
        sources = {
            'formatted.md': ('# **Alice &amp; Bob** [reference](https://example.test) `&lt;raw&gt;`',
                             'Alice & Bob reference &lt;raw&gt;'),
            'fenced.md': ('```markdown\n# Fenced fake\n```\n<!--\n# Hidden fake\n-->\n## Not H1\n# **Real** [title](https://example.test)\n# Later',
                          'Real title'),
            'unclosed.md': ('```markdown\n# Fenced fake', 'Unclosed'),
            'no-heading.md': ('- # A list item\n\n<h1>Raw HTML</h1>', 'No-Heading'),
            'hostile.md': ('# &lt;img src=x onerror=alert(1)&gt; **Safe** &#39;',
                           "<img src=x onerror=alert(1)> Safe '"),
            'unmatched.md': ('# Unmatched `code', 'Unmatched `code'),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, (source, _) in sources.items():
                (root / name).write_text(source, encoding='utf-8')
            build_catalog(root, CFG)
            records = {record['url']: record for record in json.loads((root / 'search-index.json').read_text(encoding='utf-8'))}
            fallback = TextCollector()
            fallback.feed((root / 'search.html').read_text(encoding='utf-8'))
            for name, (_, title) in sources.items():
                with self.subTest(name=name):
                    self.assertEqual(records['/' + name]['title'], title)
                    self.assertIn(title, ''.join(fallback.text))
            self.assertNotIn('img', fallback.tags)
            self.assertNotIn('strong', fallback.tags)

    def test_ascii_email_structure_and_length_matrix(self):
        longest_domain = '.'.join(('a' * 63, 'b' * 63, 'c' * 63, 'd' * 60))
        accepted = ('alice@example.com', "O'Neil+news@example-domain.com",
                    "!#$%&'*+-/=?^_`{|}~@example.test", 'first.last@sub.example.test',
                    'User@EXAMPLE.COM', 'user@xn--bcher-kva.example',
                    'user@example.xn--p1ai', 'a' * 64 + '@example.test',
                    'a@' + longest_domain)
        rejected = ('', 'a@..com', '.a@example.com', 'a.@example.com',
                    'a..b@example.com', 'a@example..com', 'a@-example.com',
                    'a@example-.com', 'a@example.com.', 'a@.example.com',
                    'a@example_com.test', 'a@localhost', 'a@[127.0.0.1]',
                    'a b@example.com', ' a@example.com', 'a@example.com\n',
                    'a@b@example.com', 'a@', '@example.com', 'a@café.test',
                    'café@example.test', '"a b"@example.com',
                    'a' * 65 + '@example.test', 'a@' + 'b' * 64 + '.test',
                    'aa@' + longest_domain, None, 42)
        for value in accepted:
            with self.subTest(accepted=value):
                validate_email_address(value)
        for value in rejected:
            with self.subTest(rejected=value), self.assertRaises(ValueError):
                validate_email_address(value)

    def test_supported_email_punctuation_is_encoded_in_actual_contact_links(self):
        repo = Path(__file__).resolve().parents[1]
        cfg = json.loads((repo / 'site.config.example.json').read_text(encoding='utf-8'))
        cfg['EMAIL'] = "a?tag#literal%+x@example.test"
        validate_public_contacts(cfg)
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / 'site'
            build_site_staged(str(repo / 'template'), str(site), dict(cfg, **json_block(cfg)))
            for filename in ('index.html', '404.html', 'writing/example-depth-page.html'):
                document = Document()
                document.feed((site / filename).read_text(encoding='utf-8'))
                links = [urlsplit(link) for link in document.links if link.startswith('mailto:')]
                self.assertEqual(len(links), 1)
                self.assertEqual(unquote(links[0].path), cfg['EMAIL'])
                self.assertEqual(links[0].query, '')
                self.assertEqual(links[0].fragment, '')

    def test_article_and_search_share_authored_and_configured_entity_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / 'template'
            (template / 'writing').mkdir(parents=True)
            source = ('# Entity policy\n\nAuthored &amp; &lt; &#39; &#xA9; &amp;lt;\n\n'
                      'Configured {{FULL_NAME}}\n\nInline `&amp; &lt; &#39;`\n\n'
                      '````html\n```\nFenced &amp; &lt; &#39;\n<!-- literal -->\n````\n'
                      '\nEscaped &lt;img src=x onerror=alert(1)&gt;\n')
            (template / 'writing' / 'entities.md').write_text(source, encoding='utf-8')
            site = root / 'site'
            build_site_staged(str(template), str(site), {**CFG, 'FULL_NAME': "Alice & Bob's"})
            parsed = TextCollector()
            parsed.feed((site / 'writing' / 'entities.html').read_text(encoding='utf-8'))
            rendered = ''.join(parsed.text)
            indexed = json.loads((site / 'search-index.json').read_text(encoding='utf-8'))[0]['text']
            for phrase in ("Authored & < ' © &lt;", "Configured Alice & Bob's",
                           'Inline &amp; &lt; &#39;', 'Fenced &amp; &lt; &#39;',
                           '<!-- literal -->', 'Escaped <img src=x onerror=alert(1)>'):
                with self.subTest(phrase=phrase):
                    self.assertIn(phrase, rendered)
                    self.assertIn(phrase, indexed)
            self.assertNotIn('img', parsed.tags)

    def test_inline_code_is_literal_before_comments_links_and_formatting(self):
        code = '&amp; <!-- literal --> **bold** [x](https://example.test)'
        rendered = md_to_html('Inline `' + code + '` and [code `&amp;`](https://example.test/page)')
        parsed = TextCollector()
        parsed.feed(rendered)
        self.assertIn(code, ''.join(parsed.text))
        self.assertEqual(parsed.tags.count('a'), 1)
        self.assertNotIn('strong', parsed.tags)
        self.assertIn('<a href="https://example.test/page">code <code>&amp;amp;</code></a>', rendered)

    def test_configured_discovery_text_is_readable_searchable_and_inert(self):
        name = "Alice & Bob's <img src=x onerror=alert(1)>"
        topic = "Research & development's </script><script>alert(1)</script>"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / 'template'
            (template / 'writing').mkdir(parents=True)
            (template / 'profile.md').write_text('# {{FULL_NAME}}\n\n{{FULL_NAME}} works in {{JOB_TITLE}}.', encoding='utf-8')
            (template / 'writing' / 'article.md').write_text(
                '<!--\ntitle: {{FULL_NAME}}\ndesc: About {{FULL_NAME}}\nabout: {{JOB_TITLE}}\n-->\n'
                '# {{FULL_NAME}}\n\n{{FULL_NAME}}\n\n````html\n```\n&lt;literal&gt; &amp; &#x27;\n<!-- literal comment -->\n````\n'
                '<!-- hidden guidance -->', encoding='utf-8')
            site = root / 'site'
            build_site_staged(str(template), str(site), {**CFG, 'FULL_NAME': name, 'JOB_TITLE': topic})
            records = json.loads((site / 'search-index.json').read_text(encoding='utf-8'))
            for record in records:
                self.assertEqual(record['title'], name)
                self.assertIn(name, record['text'])
                self.assertIn("alice & bob's", (record['title'] + record['text']).lower())
            article = next(record for record in records if record['url'].endswith('article.html'))
            self.assertIn('&lt;literal&gt; &amp; &#x27;', article['text'])
            self.assertIn('<!-- literal comment -->', article['text'])
            self.assertNotIn('hidden guidance', article['text'])
            for filename in ('writing.html', 'search.html', 'writing/article.html'):
                content = (site / filename).read_text(encoding='utf-8')
                parsed = TextCollector()
                parsed.feed(content)
                self.assertIn(name, ''.join(parsed.text))
                self.assertNotIn('img', parsed.tags)
                self.assertNotIn('onerror="', content)
                self.assertEqual(parsed.tags.count('script'), 0 if filename == 'writing.html' else 1)
                self.assertNotIn('Alice &amp;amp;', content)
            feed = ET.fromstring((site / 'feed.xml').read_bytes())
            ns = {'a': 'http://www.w3.org/2005/Atom'}
            self.assertEqual(feed.find('a:entry/a:title', ns).text, name)
            self.assertEqual(feed.find('a:entry/a:summary', ns).text, 'About ' + name)
            self.assertEqual(feed.find('a:author/a:name', ns).text, name)
            self.assertIsNone(feed.find('.//img'))
            for filename in ('writing.md', 'search.md'):
                self.assertNotIn('<img', (site / filename).read_text(encoding='utf-8'))

    def test_artifact_audit_rejects_truncated_json_ld(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for data in ('{"name":', '{"name":"Example"}'):
                with self.subTest(data=data):
                    (root / 'index.html').write_text('<script type="application/ld+json">' + data, encoding='utf-8')
                    build_inventory(root, CFG)
                    self.assertIn('unterminated JSON-LD', '\n'.join(audit(root)))
            (root / 'index.html').write_text('<script type="application/ld+json">{"name":"Example"}</script>', encoding='utf-8')
            build_inventory(root, CFG)
            self.assertEqual(audit(root), [])

    def test_artifact_audit_normalizes_same_origin_hosts_and_ports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for url in ('https://EXAMPLE.TEST/missing.html', 'https://EXAMPLE.TEST:443/missing.html'):
                with self.subTest(url=url):
                    (root / 'index.html').write_text('<a href="' + url + '">Missing</a>', encoding='utf-8')
                    build_inventory(root, CFG)
                    self.assertIn('missing local target', '\n'.join(audit(root)))
            (root / 'index.html').write_text('<a href="https://EXAMPLE.TEST:444/missing.html">Other service</a>', encoding='utf-8')
            build_inventory(root, CFG)
            self.assertEqual(audit(root), [])
            (root / 'index.html').write_text('<h1 id="exists">Title</h1><a href="https://EXAMPLE.TEST:443/#missing">Missing fragment</a>', encoding='utf-8')
            build_inventory(root, CFG)
            self.assertIn('missing local fragment', '\n'.join(audit(root)))

    def test_windows_overlap_guard_allows_separate_drives(self):
        self.assertFalse(paths_overlap(r'C:\repo\template', r'D:\temp\site', ntpath))
        self.assertFalse(paths_overlap(r'C:\repo\template', r'C:\repo\site', ntpath))
        for template, output in ((r'C:\repo\template', r'C:\repo\template'),
                                 (r'C:\repo\template', r'C:\repo\template\site'),
                                 (r'C:\repo\template', r'C:\repo'),
                                 (r'C:\REPO\template', r'c:\repo\TEMPLATE\site')):
            with self.subTest(template=template, output=output):
                self.assertTrue(paths_overlap(template, output, ntpath))

    def test_search_preserves_closed_and_unclosed_fenced_html_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            source = '# Examples\n````html\n```\n<!-- closed literal -->\n<!-- unclosed literal\n````\nVisible afterward\n<!-- hidden guidance -->'
            (root / 'writing' / 'comments.md').write_text(source, encoding='utf-8')
            build_catalog(root, CFG)
            records = json.loads((root / 'search-index.json').read_text(encoding='utf-8'))
            text = records[0]['text']
            self.assertIn('<!-- closed literal -->', text)
            self.assertIn('<!-- unclosed literal', text)
            self.assertIn('Visible afterward', text)
            self.assertNotIn('hidden guidance', text)

    def test_shorter_inner_fence_keeps_literal_comments_and_hides_guidance(self):
        source = '````markdown\n```\n<!-- literal after shorter fence -->\n````\n<!-- author guidance should be omitted -->\n'
        self.assertEqual(md_to_html(source), '<pre><code class="language-markdown">```\n&lt;!-- literal after shorter fence --&gt;</code></pre>')

    def test_comment_removal_and_renderer_share_fence_boundaries(self):
        for ending in ('````', '`````'):
            with self.subTest(ending=ending):
                source = '<!-- guidance\n```\n-->\n````html\n<!-- literal\n```\n-->\n' + ending + '\n<!-- hidden -->\n# Visible'
                result = md_to_html(source)
                self.assertIn('&lt;!-- literal\n```\n--&gt;', result)
                self.assertNotIn('guidance', result)
                self.assertNotIn('hidden', result)
                self.assertTrue(result.endswith('<h1>Visible</h1>'))

    def test_feed_escapes_metadata_and_omits_unknown_publication_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            (root / 'writing' / 'article.md').write_text('<!--\ntitle: <Sample> & notes\nupdated: 2025-12-20\n-->\n# Article', encoding='utf-8')
            build_catalog(root, CFG)
            feed = ET.fromstring((root / 'feed.xml').read_bytes())
            ns = {'a': 'http://www.w3.org/2005/Atom'}
            self.assertEqual(feed.find('a:entry/a:title', ns).text, '<Sample> & notes')
            self.assertEqual(feed.find('a:entry/a:updated', ns).text, '2025-12-20T00:00:00Z')
            self.assertIsNone(feed.find('a:entry/a:published', ns))

    def test_artifact_audit_rejects_active_html_and_malformed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('<script src="data:text/javascript,alert(1)"></script><p onclick="evil">Text</p>', encoding='utf-8')
            build_inventory(root, CFG)
            errors = '\n'.join(audit(root))
            self.assertIn('data URL', errors)
            self.assertIn('event-handler', errors)
            (root / 'content-manifest.json').write_text('[]', encoding='utf-8')
            self.assertIn('must be an object', audit(root)[0])

    def test_artifact_audit_checks_fragments_links_and_current_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'index.html'
            path.write_text('<h1 id="hello">Hello</h1><a href="#hello">Jump</a>', encoding='utf-8')
            build_inventory(root, CFG)
            self.assertEqual(audit(root), [])
            path.write_text('<a href="/missing.html">Broken</a><a href="#absent">Jump</a>', encoding='utf-8')
            errors = '\n'.join(audit(root))
            self.assertIn('inventory differs', errors)
            self.assertIn('missing local target', errors)
            self.assertIn('missing local fragment', errors)

    def test_inventory_is_deterministic_and_detects_byte_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('Example', encoding='utf-8')
            build_inventory(root, CFG)
            first = (root / 'content-manifest.json').read_bytes()
            build_inventory(root, CFG)
            self.assertEqual(first, (root / 'content-manifest.json').read_bytes())
            (root / 'index.html').write_text('Changed', encoding='utf-8')
            self.assertNotEqual(json.loads(first)['files'], inventory(root))
            with patch('build_inventory.MAX_FILE_BYTES', 1), self.assertRaises(ValueError):
                inventory(root)

    def test_build_cannot_replace_or_publish_its_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for output in (root, root / 'site'):
                with self.assertRaisesRegex(ValueError, 'overlap'):
                    build_site_staged(str(root), str(output), CFG)

    def test_publication_dates_are_explicit_and_calendar_valid(self):
        page = render_page('test', '# Example', CFG)
        self.assertNotIn('datePublished', page)
        page = render_page('test', '<!--\npublished: 2025-12-01\nupdated: 2025-12-20\n-->\n# Example', CFG)
        self.assertIn('"datePublished": "2025-12-01"', page)
        self.assertIn('"dateModified": "2025-12-20"', page)
        with self.assertRaises(ValueError):
            render_page('test', '<!--\npublished: 2026-02-30\n-->\n# Example', CFG)
        with self.assertRaises(ValueError):
            render_page('test', '<!--\npublished: 2026-02-01\n-->\n# Example', CFG)

    def test_search_indexes_published_text_without_author_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'profile.md').write_text('# Example\n<!-- do not publish guidance -->\nVerified words', encoding='utf-8')
            build_catalog(root, CFG)
            records = json.loads((root / 'search-index.json').read_text())
            self.assertEqual(records[0]['url'], '/profile.md')
            self.assertIn('Verified words', records[0]['text'])
            self.assertNotIn('guidance', records[0]['text'])
            self.assertIn('/profile.md', (root / 'search.html').read_text())

    def test_writing_directory_tracks_sources_and_empty_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_catalog(root, CFG)
            self.assertIn('No writing pages', (root / 'writing.html').read_text())
            (root / 'writing').mkdir()
            (root / 'writing' / 'a & b.md').write_text('<!--\ntitle: <New>\ndesc: Real description\nabout: Topic\n-->\n# Article', encoding='utf-8')
            build_catalog(root, CFG)
            page = (root / 'writing.html').read_text(encoding='utf-8')
            self.assertIn('a%20%26%20b.html', page)
            self.assertIn('&lt;New&gt;', page)
            self.assertIn('Real description', page)

    def test_outline_has_unique_working_fragments(self):
        page = render_page('test', '# Test\n## Evidence\n## Evidence\n## Main content\n```\n## Hidden\n```', CFG)
        for identifier in ('evidence', 'evidence-2', 'main-content-2'):
            self.assertIn('href="#%s"' % identifier, page)
            self.assertIn('id="%s"' % identifier, page)
        self.assertNotIn('href="#hidden"', page)
        self.assertIn('<main id="main-content">', page)

    def test_fences_are_literal_and_unclosed_fences_terminate(self):
        source = '```html\n<!-- visible -->\n<script>bad()</script>\n[link](https://example.test)\n```\n<!-- hidden -->'
        page = md_to_html(source)
        self.assertIn('&lt;!-- visible --&gt;', page)
        self.assertNotIn('hidden', page)
        self.assertNotIn('<script>', page)
        self.assertNotIn('<a ', page)
        self.assertIn('<pre><code>tail</code></pre>', md_to_html('```\ntail'))

    def test_article_metadata_cannot_terminate_script_or_attribute(self):
        attack = '</script><script>alert(1)</script>'
        page = render_page("test", '<!--\ntitle: ' + attack + '\n-->\n# Test',
                           {**CFG, "FULL_NAME": attack, "EMAIL": 'x" onclick="evil'})
        self.assertEqual(page.count("</script>"), 1)
        self.assertNotIn(' onclick="', page)
        import re
        metadata = json.loads(re.search(r'application/ld\+json">(.*?)</script>', page, re.S)[1])
        self.assertEqual(metadata["headline"], attack)

    def test_contact_routes_are_validated(self):
        validate_public_contacts(CFG)
        for key, value in (("EMPLOYER_URL", "javascript:alert(1)"),
                           ("EMPLOYER_URL", "https://user:pass@example.test"),
                           ("EMAIL", 'person@example.test" onclick="evil'),
                           ("X_HANDLE", "person?other"), ("LINKEDIN_SLUG", "../other")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_public_contacts({**CFG, key: value})


if __name__ == "__main__":
    unittest.main()

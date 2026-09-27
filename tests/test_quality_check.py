from __future__ import annotations

import json
import html
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import quote
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QualityCheckTests(unittest.TestCase):
    def test_malformed_routes_retain_suffixes_in_source_and_rendered_contexts(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / 'scripts', repo / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / 'template', repo / 'template')
            cfg = json.loads((ROOT / 'site.config.example.json').read_text(encoding='utf-8'))
            cfg['EMAIL'] = "o'hara@yourname.com"
            (repo / 'site.config.json').write_text(json.dumps(cfg), encoding='utf-8')
            address = 'o%27hara%40yourname.com'
            route = 'mailto:' + address
            malformed = [
                '[Contact](' + route + "'evil)", '<' + route + "'evil>",
                route + "'evil", route + "'", "'" + route + "'evil",
                "'" + route + "'evil'", "'" + route + "'.evil'",
                '"' + route + '"evil', '"' + route + '"evil"',
                '[Contact](' + route + '%27evil)',
            ]
            for filename in ('contact.md', 'writing/example-depth-page.md'):
                path = repo / 'template' / filename
                original = path.read_text(encoding='utf-8')
                for addition in malformed:
                    with self.subTest(filename=filename, addition=addition):
                        path.write_text(original + '\n' + addition + '\n', encoding='utf-8')
                        build = subprocess.run([sys.executable, str(repo / 'scripts' / 'build.py')], cwd=repo,
                                               capture_output=True, text=True, check=False)
                        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                        self.assertIn(addition, (repo / 'site' / filename).read_text(encoding='utf-8'))
                        if filename.startswith('writing/') and addition.startswith('[Contact]('):
                            rendered = html.unescape((repo / 'site' / filename).with_suffix('.html').read_text(encoding='utf-8'))
                            self.assertIn(addition[len('[Contact]('):-1], rendered)
                        result = subprocess.run([sys.executable, str(repo / 'scripts' / 'quality_check.py')],
                                                cwd=repo, capture_output=True, text=True, check=False)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn('email:', result.stdout)
                path.write_text(original, encoding='utf-8')

    def test_apostrophe_routes_pass_full_build_and_gate_with_prose_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / 'scripts', repo / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / 'template', repo / 'template')
            cfg = json.loads((ROOT / 'site.config.example.json').read_text(encoding='utf-8'))
            command = [sys.executable, str(repo / 'scripts' / 'quality_check.py')]
            for local in ("o'hara", "'first", "last'", "o'%2Fhara"):
                email = local + '@yourname.com'
                cfg['EMAIL'] = email
                (repo / 'site.config.json').write_text(json.dumps(cfg), encoding='utf-8')
                build = subprocess.run([sys.executable, str(repo / 'scripts' / 'build.py')], cwd=repo,
                                       capture_output=True, text=True, check=False)
                self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                path = repo / 'site' / 'contact.md'
                original = path.read_text(encoding='utf-8')
                for address in (quote(email, safe="@'"), quote(email, safe='@'), quote(email, safe="'")):
                    patterns = ['mailto:%s', '[Contact](mailto:%s)', '<mailto:%s>']
                    patterns += [left + 'mailto:%s' + right + punctuation
                                 for left, right in (("'", "'"), ('"', '"'), ("('", "')"), ("['", "']"))
                                 for punctuation in ('', ',', '.', ';', ':', '!', '?', ').')]
                    patterns += ["'mailto:%s?subject=Hello#draft',"]
                    patterns += [marks + quoted + marks[::-1]
                                 for marks in ('**', '_', '`', '``', '**_')
                                 for quoted in ("'mailto:%s'", '"mailto:%s"')]
                    with self.subTest(email=email, address=address):
                        routes = '\n'.join(pattern % address for pattern in patterns)
                        routes += "\n'mailto:" + address + "','mailto:" + address + "'\n"
                        path.write_text(original + '\n' + routes + '\n', encoding='utf-8')
                        result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                encoded = quote(email, safe='@')
                for address in ("other'hara@unrelated.example", 'other%27hara@unrelated.example',
                                encoded + '.', encoded + ',', encoded + '.evil',
                                encoded + ',other@unrelated.example',
                                encoded + "', 'mailto:other@unrelated.example"):
                    with self.subTest(divergent=address):
                        path.write_text(original + "\n'mailto:" + address + "',\n", encoding='utf-8')
                        result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn('email:', result.stdout)

    def test_supported_email_matrix_passes_full_build_and_required_gate(self):
        punctuation = "!#$%&'*+-/=?^_`{|}~"
        addresses = ["a" + mark + "tag@yourname.com" for mark in punctuation]
        addresses += ["a" + punctuation + "tag@yourname.com", "a%2Ftag@yourname.com",
                      "a%252Ftag@yourname.com", "a**tag@yourname.com",
                      "a?tag@contacts.example", "a^tag@yourname.com.evil"]
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / 'scripts', repo / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / 'template', repo / 'template')
            cfg = json.loads((ROOT / 'site.config.example.json').read_text(encoding='utf-8'))
            for email in addresses:
                with self.subTest(email=email):
                    cfg['EMAIL'] = email
                    (repo / 'site.config.json').write_text(json.dumps(cfg), encoding='utf-8')
                    for script in ('build.py', 'quality_check.py'):
                        result = subprocess.run([sys.executable, str(repo / 'scripts' / script)], cwd=repo,
                                                capture_output=True, text=True, check=False)
                        self.assertEqual(result.returncode, 0, email + ': ' + script + '\n' + result.stdout + result.stderr)
                    contact = repo / 'site' / 'contact.md'
                    contact.write_text(contact.read_text(encoding='utf-8') + '\n[Contact](mailto:' + quote(email, safe='@') + ')\n', encoding='utf-8')
                    result = subprocess.run([sys.executable, str(repo / 'scripts' / 'quality_check.py')], cwd=repo,
                                            capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 0, email + ': Markdown mailto\n' + result.stdout + result.stderr)

    def test_required_gate_rejects_divergent_routes_and_contact_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / 'scripts', repo / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / 'template', repo / 'template')
            cfg = json.loads((ROOT / 'site.config.example.json').read_text(encoding='utf-8'))
            cfg['EMAIL'] = 'a%2Ftag@contacts.example'
            (repo / 'site.config.json').write_text(json.dumps(cfg), encoding='utf-8')
            build = subprocess.run([sys.executable, str(repo / 'scripts' / 'build.py')], cwd=repo,
                                   capture_output=True, text=True, check=False)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            command = [sys.executable, str(repo / 'scripts' / 'quality_check.py')]
            mutations = {
                'index.html': '<p><a href="mailto:other@unrelated.example">Contact</a></p>',
                '404.html': '<p><a href="mailto:other@contacts.example">Contact</a></p>',
                'writing/example-depth-page.html': '<p><a href="mailto:other%3Ftag@contacts.example">Contact</a></p>',
                'contact.md': '\nIncorrect contact: other?tag@contacts.example\n',
                'profile.md': '\nIncorrect contact: other^tag@yourname.com\n',
                'writing.html': '<p>Incorrect contact: other<span>^tag</span>@contacts.example</p>',
                'search.html': '<p><a href="mailto:a%252Ftag@contacts.example\',">Contact</a></p>',
            }
            for filename, addition in mutations.items():
                with self.subTest(filename=filename):
                    path = repo / 'site' / filename
                    original = path.read_text(encoding='utf-8')
                    path.write_text(original + addition, encoding='utf-8')
                    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('email:', result.stdout)
                    path.write_text(original, encoding='utf-8')
            index = repo / 'site' / 'index.html'
            original = index.read_text(encoding='utf-8')
            for email in ('other@example.invalid', "a%2Ftag@contacts.example',"):
                with self.subTest(structured=email):
                    index.write_text(original.replace('"email": "a%2Ftag@contacts.example"',
                                                      '"email": ' + json.dumps(email)), encoding='utf-8')
                    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('email:', result.stdout)
            index.write_text(original, encoding='utf-8')
            article = repo / 'site' / 'writing' / 'example-depth-page.md'
            article.write_text(article.read_text(encoding='utf-8') + '\nThird-party example: other@yourname.com.evil\n', encoding='utf-8')
            result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def run_quality_check(
        self,
        writing_as_file: bool = False,
        live: bool = False,
        domain: str = "example.test",
        path: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            scripts = repo / "scripts"
            scripts.mkdir()
            shutil.copy2(ROOT / "scripts" / "a2a_agent_card.py", scripts)
            shutil.copy2(ROOT / "scripts" / "build_sitemap.py", scripts)
            shutil.copy2(ROOT / "scripts" / "http_client.py", scripts)
            shutil.copy2(ROOT / "scripts" / "llms_txt.py", scripts)
            shutil.copy2(ROOT / "scripts" / "quality_check.py", scripts)
            shutil.copy2(ROOT / "scripts" / "email_addresses.py", scripts)

            site = repo / "site"
            site.mkdir()
            (site / "index.html").write_text(
                '<!doctype html>\n'
                '<link rel="alternate" type="text/markdown" href="/profile.md">\n'
                '<link rel="describedby" href="/llms.txt">\n',
                encoding="utf-8",
            )
            (site / "profile.md").write_text(
                "# Example profile\n\nLast updated: 2026-08-30\n",
                encoding="utf-8",
            )
            (site / "profile.html").write_text(
                '<!doctype html>\n'
                '<link rel="alternate" type="text/markdown" href="/profile.md">\n'
                '<link rel="describedby" href="/llms.txt">\n',
                encoding="utf-8",
            )
            (site / "search-index.json").write_text(
                json.dumps([{"title": "Example profile", "url": "/profile.html",
                             "text": "Example profile", "type": "page"}]),
                encoding="utf-8",
            )
            (site / "search.md").write_text(
                "# Search and page directory\n\nLast updated: 2026-08-30\n\n"
                "- [Example profile](/profile.html)\n",
                encoding="utf-8",
            )
            (site / "feed.xml").write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<feed xmlns="http://www.w3.org/2005/Atom">'
                "<id>https://%s/feed.xml</id>"
                "<title>Example writing</title>"
                '<link href="https://%s/feed.xml" rel="self"/>'
                '<link href="https://%s/"/>'
                '<author><name>Example</name></author>'
                "<entry>"
                "<id>https://%s/profile.html</id>"
                "<title>Example profile</title>"
                '<link href="https://%s/profile.html"/>'
                "<updated>2026-08-30T00:00:00Z</updated>"
                "</entry>"
                "<updated>2026-08-30T00:00:00Z</updated>"
                "</feed>\n" % ((domain,) * 5),
                encoding="utf-8",
            )
            (site / "llms.txt").write_text(
                "# Example\n\n"
                "## Start here\n\n"
                "- [Profile](https://%s/profile.md): Canonical profile.\n" % domain,
                encoding="utf-8",
            )
            (site / "robots.txt").write_text(
                "User-agent: *\nAllow: /\n\nSitemap: https://%s/sitemap.xml\n" % domain,
                encoding="utf-8",
            )
            (site / "sitemap.xml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                "  <url>\n"
                "    <loc>https://%s/</loc>\n"
                "    <lastmod>2026-08-30</lastmod>\n"
                "  </url>\n"
                "  <url>\n"
                "    <loc>https://%s/llms.txt</loc>\n"
                "    <lastmod>2026-08-30</lastmod>\n"
                "  </url>\n"
                "  <url>\n"
                "    <loc>https://%s/profile.md</loc>\n"
                "    <lastmod>2026-08-30</lastmod>\n"
                "  </url>\n"
                "  <url>\n"
                "    <loc>https://%s/profile.html</loc>\n"
                "    <lastmod>2026-08-30</lastmod>\n"
                "  </url>\n"
                "  <url>\n"
                "    <loc>https://%s/search.md</loc>\n"
                "    <lastmod>2026-08-30</lastmod>\n"
                "  </url>\n"
                "</urlset>\n" % (domain, domain, domain, domain, domain),
                encoding="utf-8",
            )
            if writing_as_file:
                (site / "writing").write_text("not a directory\n", encoding="utf-8")

            (repo / "site.config.json").write_text(
                json.dumps({"DOMAIN": domain, "LAST_UPDATED": "2026-08-30"}),
                encoding="utf-8",
            )
            command = [sys.executable, str(scripts / "quality_check.py")]
            if live:
                command.append("--live")
            env = os.environ.copy()
            if path is not None:
                env["PATH"] = path
                env.update(
                    {
                        "ALL_PROXY": "",
                        "HTTPS_PROXY": "",
                        "NO_PROXY": "*",
                        "all_proxy": "",
                        "https_proxy": "",
                        "no_proxy": "*",
                    }
                )
            return subprocess.run(
                command,
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

    def test_site_without_writing_directory_passes_quality_check(self) -> None:
        result = self.run_quality_check()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_non_directory_writing_path_does_not_crash_quality_check(self) -> None:
        result = self.run_quality_check(writing_as_file=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_live_check_does_not_require_curl_executable(self) -> None:
        source = (ROOT / "scripts" / "quality_check.py").read_text(encoding="utf-8")
        self.assertNotIn("curl.exe", source)

        result = self.run_quality_check(
            live=True,
            domain="127.0.0.1:9",
            path="",
        )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("9. LIVE: LINKS AND SITEMAP", result.stdout)
        self.assertIn(
            "A2A is disabled locally but the live Agent Card path returned",
            result.stdout,
        )
        self.assertIn("FAILURES:", result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("FileNotFoundError", result.stderr)

    def test_search_index_and_static_directory_drift_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "template", repo / "template")
            (repo / "site.config.json").write_text(
                (ROOT / "site.config.example.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
            build = subprocess.run([sys.executable, str(repo / "scripts" / "build.py")], cwd=repo,
                                   capture_output=True, text=True, check=False)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)

            def run_gate() -> subprocess.CompletedProcess[str]:
                return subprocess.run([sys.executable, str(repo / "scripts" / "quality_check.py")],
                                      cwd=repo, capture_output=True, text=True, check=False)

            passed = run_gate()
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertIn("search-index.json and search.md describe the same built pages", passed.stdout)

            index_path = repo / "site" / "search-index.json"
            directory_path = repo / "site" / "search.md"
            original_index = index_path.read_text(encoding="utf-8")
            original_directory = directory_path.read_text(encoding="utf-8")

            records = json.loads(original_index)
            stale = dict(records[0], url="/removed-page.html")
            index_path.write_text(json.dumps([stale] + records), encoding="utf-8")
            result = run_gate()
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("search-index.json links to a missing build artifact /removed-page.html", result.stdout)
            index_path.write_text(original_index, encoding="utf-8")

            directory_path.write_text(original_directory.replace("- [About this site](/about.html)\n", ""), encoding="utf-8")
            result = run_gate()
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("search.md and search-index.json disagree about ['/about.html']", result.stdout)
            directory_path.write_text(original_directory, encoding="utf-8")

            index_path.unlink()
            result = run_gate()
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("search-index.json is missing or invalid", result.stdout)

    def test_atom_feed_drift_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "template", repo / "template")
            (repo / "site.config.json").write_text(
                (ROOT / "site.config.example.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
            build = subprocess.run([sys.executable, str(repo / "scripts" / "build.py")], cwd=repo,
                                   capture_output=True, text=True, check=False)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)

            def run_gate() -> subprocess.CompletedProcess[str]:
                return subprocess.run([sys.executable, str(repo / "scripts" / "quality_check.py")],
                                      cwd=repo, capture_output=True, text=True, check=False)

            passed = run_gate()
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertIn("feed.xml is a valid Atom feed for yourname.com", passed.stdout)

            feed_path = repo / "site" / "feed.xml"
            original = feed_path.read_text(encoding="utf-8")
            name = json.loads((ROOT / "site.config.example.json").read_text(encoding="utf-8"))["FULL_NAME"]
            broken = [
                (original.replace("2026-01-01T00:00:00Z", "2026-01-01"),
                 "is not an RFC 3339 UTC timestamp"),
                (original.replace("<title>%s writing</title>" % name, "<title></title>"),
                 "feed.xml has no <title>"),
                (original.replace('rel="self"', 'rel="alternate"'),
                 "must declare one rel=self link"),
            ]
            for text, message in broken:
                with self.subTest(message=message):
                    feed_path.write_text(text, encoding="utf-8")
                    result = run_gate()
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(message, result.stdout)

            stale = original.replace("/writing/example-depth-page.html", "/writing/removed.html")
            feed_path.write_text(stale, encoding="utf-8")
            result = run_gate()
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("links to a missing build artifact /writing/removed.html", result.stdout)
            feed_path.write_text(original, encoding="utf-8")


    def test_structured_data_defects_fail_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "template", repo / "template")
            (repo / "site.config.json").write_text(
                (ROOT / "site.config.example.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
            build = subprocess.run([sys.executable, str(repo / "scripts" / "build.py")], cwd=repo,
                                   capture_output=True, text=True, check=False)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)

            def run_gate() -> subprocess.CompletedProcess[str]:
                return subprocess.run([sys.executable, str(repo / "scripts" / "quality_check.py")],
                                      cwd=repo, capture_output=True, text=True, check=False)

            passed = run_gate()
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertIn("index.html", passed.stdout)

            index_path = repo / "site" / "index.html"
            original = index_path.read_text(encoding="utf-8")
            broken = [
                (original.replace('"@context": "https://schema.org"', '"@context": "https://example.invalid/vocab"'),
                 "index.html does not declare the schema.org context"),
                (original.replace('"@type": "FAQPage",', ""),
                 "index.html has a JSON-LD node with no @type"),
                (original.replace('"@id": "https://yourname.com/#faq"',
                                  '"@id": "https://yourname.com/#person"'),
                 "index.html declares @id https://yourname.com/#person more than once"),
            ]
            for text, message in broken:
                with self.subTest(message=message):
                    index_path.write_text(text, encoding="utf-8")
                    result = run_gate()
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(message, result.stdout)
            index_path.write_text(original, encoding="utf-8")


    def test_robots_sitemap_directive_drift_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "template", repo / "template")
            (repo / "site.config.json").write_text(
                (ROOT / "site.config.example.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
            build = subprocess.run([sys.executable, str(repo / "scripts" / "build.py")], cwd=repo,
                                   capture_output=True, text=True, check=False)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)

            def run_gate() -> subprocess.CompletedProcess[str]:
                return subprocess.run([sys.executable, str(repo / "scripts" / "quality_check.py")],
                                      cwd=repo, capture_output=True, text=True, check=False)

            passed = run_gate()
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertIn("ok   robots.txt points crawlers at https://yourname.com/sitemap.xml",
                          passed.stdout)

            robots_path = repo / "site" / "robots.txt"
            original = robots_path.read_text(encoding="utf-8")
            broken = [
                (original.replace("https://yourname.com/sitemap.xml", "https://www.yourname.com/sitemap.xml"),
                 "robots.txt Sitemap is https://www.yourname.com/sitemap.xml, "
                 "not https://yourname.com/sitemap.xml"),
                (original.replace("Sitemap: https://yourname.com/sitemap.xml\n", ""),
                 "robots.txt declares no Sitemap"),
                (original.replace("User-agent: *\nAllow: /", "User-agent: *\nDisallow: /"),
                 "robots.txt blocks every unspecified crawler with 'Disallow: /'"),
            ]
            for text, message in broken:
                with self.subTest(message=message):
                    robots_path.write_text(text, encoding="utf-8")
                    result = run_gate()
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(message, result.stdout)
            robots_path.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

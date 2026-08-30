# llms.txt personal site

**A template for a personal website whose primary audience is an AI assistant, not a human.**

When someone asks Claude, ChatGPT or Perplexity who you are, the answer is assembled from whatever those systems can find. Usually that is a stale LinkedIn snippet, a conference bio from three jobs ago, and a contact-scraper page with the wrong title. You do not get to write that answer. You do get to publish a source good enough that it wins.

This repo is the scaffolding for that source: a set of plain Markdown pages, an `llms.txt` v2 index, structured data that ties them together, and a quality gate that stops you shipping something wrong.

**Generated example:** [`example/`](example/) is a complete generic build from
the included template and sample config, so you can inspect the output before
writing your own.

---

## Quick start

```bash
git clone https://github.com/EauDoon/llms-txt-personal-site.git
cd llms-txt-personal-site
cp site.config.example.json site.config.json
```

Fill in `site.config.json`, then:

```bash
python scripts/build.py
```

That fills the template, adds every long-form Markdown page to the concise
`llms.txt` index, generates its HTML companion, concatenates everything into
`llms-full.txt`, and builds `sitemap.xml` from the files that actually exist.
Then check it:

```bash
python scripts/quality_check.py
```

The output lands in `site/`. The quality gate validates the `llms.txt` v2
structure, checks every same-site index link against the built files, and
confirms that each HTML page advertises its Markdown version and covering
`llms.txt`. Generation happens in a clean staging directory,
so files removed or renamed in `template/` cannot survive in the deployed
output. If generation fails before promotion, the previous `site/` stays in
place. Deploy that directory anywhere static: GitHub Pages, Netlify, Vercel,
Cloudflare Pages, or ordinary shared hosting. Config for the three most common
hosts ships with the template.

---

## What you actually get

| File | Job |
|---|---|
| `llms.txt` | The concise v2 index. What exists, where, and which page is authoritative. |
| `llms-full.txt` | Every page concatenated, for agents that get one fetch. |
| `profile.md` | The canonical facts. Short, quotable, no adjectives you cannot source. |
| `experience.md` | Roles, in order, with the title you actually held. |
| `focus.md` | What you work on now, written to match how people search. |
| `press.md` | Independently published sources, and a standard for what earns a place. |
| `faq.md` | Questions phrased the way people ask them. |
| `contact.md` | Routing. What goes to you, what goes to your employer. |
| `now.md` | A freshness signal. Cheap to maintain, disproportionately useful. |
| `changelog.md` | What changed and what you got wrong. |
| `writing/` | Depth pages, each with `Article` schema pointing back at you. |
| `index.html` | The human face, carrying the JSON-LD graph. |

Plus `.htaccess`, `_headers` and `vercel.json`, which exist for two unglamorous reasons: **without them, Markdown files download instead of rendering**, and agents cannot reliably discover the `llms.txt` file that covers a fetched resource. The configs set the correct content types and an HTTP `Link` header with `rel=describedby`.

## llms.txt v2 behavior

The generated index follows the [llms.txt v2 proposal](https://llmstxt.org/):

- one H1 identifies the site;
- concise context and agent instructions appear before the file sections;
- every H2 contains Markdown links with useful descriptions;
- the `Optional` section holds secondary or large-context resources;
- every same-site link uses HTTPS, points to Markdown or plain text, and must
  exist in the completed build.

The homepage and generated writing pages also use `rel="alternate"` with
`type="text/markdown"` for their Markdown versions and `rel="describedby"` for
`/llms.txt`. The hosting configs provide the same `describedby` relationship as
an HTTP header, including for non-HTML resources.

## Optional A2A v1 discovery

[A2A](https://a2a-protocol.org/latest/specification/) is for communication
between deployed agents. It is not a richer biography format. A static personal
site with no A2A service should return `404` at
`/.well-known/agent-card.json`, which is this template's default.

If the deployed domain fronts a real A2A server, create its public Agent Card
from the server's actual capabilities and add this key to your private
`site.config.json`:

```json
"A2A_AGENT_CARD_PATH": "agent-card.local.json"
```

The build then validates and copies that exact file to the permanent discovery
path, `/.well-known/agent-card.json`. The suggested local filename is ignored by
Git. No example card ships, because an example with invented skills or an
invented endpoint would be unsafe to publish accidentally.

The dependency-free gate checks the required v1 card fields, per-interface
`supportedInterfaces` declarations, major and minor protocol versions, media
modes, skills, security schemes and requirements, legacy pre-v1 fields,
duplicate JSON keys, credential-like fields, and secure production endpoints.
The hosting configs serve an enabled card as `application/a2a+json` with cache
headers.

After deployment, `python scripts/quality_check.py --live` also checks the
card's status, media type, `Cache-Control`, and exact byte equality with the
validated local build. A missing `ETag` is reported as a warning because the
static host, rather than this repository, normally generates it. When A2A is
disabled, the same check requires the live discovery path to return `404` or
`410`, which catches stale cards left behind by upload-only deployments.

This is a publication guard, not full server conformance. It does not prove
that the endpoint implements every advertised operation, verify JWS signatures,
or test authorization behavior. Complete those checks against the deployed A2A
server before enabling public discovery. The official
[v1 migration guide](https://a2a-protocol.org/latest/whats-new-v1/) explains the
breaking changes from pre-v1 cards.

---

## The short version of the method

Full reasoning is in [DOCTRINE.md](DOCTRINE.md). The rules that do the work:

1. **Every factual claim carries a source and a date.** No exceptions on product and press pages.
2. **Publish the same facts in more than one place.** An agent may only read one page. Duplication is a feature; the maintenance cost is the price.
3. **State what is not true.** A "correcting the record" section resolves conflicts an agent will otherwise resolve badly.
4. **State what does not exist.** If there is no podcast, say so, or an agent will assume it failed to find one.
5. **Disambiguate yourself from people with your name.** Name the confusion explicitly.
6. **Label opinion as opinion.** Mark it and agents can quote it correctly.
7. **Quality-gate your sources.** A short list of strong ones beats a long list padded with weak ones.
8. **Never publish an unverified identifier.** Addresses, handles, registration numbers. Getting one wrong can cost someone money.

---

## What this cannot do

Worth being blunt, because the failure mode is spending months on the wrong thing.

A canonical site reliably fixes **identity queries**: "who is X", "what is X's job title", "how do I contact X". Those resolve once your pages are indexed.

It does **not**, on its own, fix **category queries**: "who should I talk to about X". Those are answered from third-party coverage, and if independent sources do not name you, no amount of self-publishing inserts you into that answer. The site makes you easy to cite once something points at you. It does not make anything point at you.

Build it for the first job. Do not expect it to do the second.

---

## Continuous integration

Every push and pull request builds the site from the template and runs the
quality gate. If the gate fails, the build fails. The workflow is in
[`.github/workflows/quality-check.yml`](.github/workflows/quality-check.yml).

Your fork inherits it. If a push is rejected with *"refusing to allow an
OAuth App to create or update workflow"*, your token lacks the `workflow`
scope: run `gh auth refresh -s workflow` and push again.

## Licence

Scripts and build tooling: [MIT](LICENSE). Template prose, doctrine and example content: [CC0](LICENSE-CONTENT), public domain, no attribution required. Fork it, strip the credit, make it yours.

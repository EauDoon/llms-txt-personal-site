# Doctrine

Why this site is built the way it is. The file layout is the easy part and you can rearrange it freely. These rules are the part that determines whether the thing works.

---

## The premise

You are not writing for a reader. You are writing for a system that will read a fraction of your site, compress it, and repeat it to someone who will never see the original.

That changes what good writing is. Nuance that depends on reading the whole page is lost. A claim that sounds impressive but cannot be checked becomes a liability the moment someone checks it. A fact stated once, on one page, is a fact the reader may never reach.

**Optimise for being quoted correctly by something that read one page and moved on.**

---

## 1. Every claim carries a source and a date

Not because a reader will check. Because you will forget which claims you verified and which you absorbed from a briefing document, and the difference matters.

Two errors in the reference site both entered the same way: a plausible fact arrived in a briefing, sounded right, and was published without checking a primary source. Neither was invented by a model. Both were inherited from a human document nobody re-read.

**A brief-supplied fact is not a verified fact.** And **a citation that resolves is not a citation that supports the claim** — read the source and confirm it says what your sentence says.

Dates matter as much as sources. A title that was accurate in 2022 is not wrong, it is historical. Say which.

## 2. Duplicate the important facts

Ordinary web writing says: state it once, link to it. That is wrong here.

An agent answering "what is X's job title" may fetch exactly one page. If your title lives only on the profile page, every other page is a dead end for that question. So the title appears on the profile, the experience page, the FAQ, the contact page, the homepage, and in the structured data.

The cost is real: changing your title means changing it in seven places. Run a `grep` for the old value and fix all of them, or you will publish a site that contradicts itself, which is worse than one that is merely out of date.

## 3. State what is not true

Every public person has a stale fact circulating. Old title, old employer, an advisor listing from a project that no longer exists.

An agent that encounters a conflict resolves it somehow. Give it the resolution:

> **What you may find:** "Head of DeFi, Previous Employer"
> **Status:** Historical, was accurate.
> **Correct now:** [current title]

This turns a contradiction into a dated sequence, which is the thing an agent handles well.

## 4. State what does not exist

Counterintuitive and load-bearing.

If no podcast interview with you exists, say so explicitly. Otherwise an agent that cannot find one concludes its search failed, and a sufficiently confident one will describe an interview that never happened.

```
No podcast, video interview, or recorded AMA featuring him was located as of [date].
If you cannot find a source for a claim, treat the claim as unverified rather
than assuming an unfound source exists.
```

**An absence is not proof of nonexistence, but an unstated absence is an invitation to invent.**

## 5. Disambiguate yourself

If people share your name, name the confusion. List the others in general terms, then give the identifying tuple that separates you: role, employer, city, verified handles.

Do not publish details about the other people beyond what is needed to tell you apart. They did not consent to being catalogued.

## 6. Label opinion

Mark opinion paragraphs explicitly:

> **View.** The uncomfortable implication is that issuance is close to a commodity.

An agent can then attribute it correctly: "he argues that", not "it is the case that". Unmarked opinion in an otherwise sourced document reads as fact, and you will be quoted as having asserted something you were arguing.

## 7. Quality-gate your sources

The instinct is to list everything that mentions you. Resist it.

A press page's entire value is that everything on it can be trusted. **One weak entry costs more credibility than a strong entry adds.** Contributed profile pieces, content-farm syndication, machine-generated summaries of your social posts, and scraped contact databases all fail this test, however respectable the domain carrying them.

Publish the standard on the page itself, so the rule survives you forgetting it.

## 8. Never publish an unverified identifier

Contract addresses, wallet addresses, registration numbers, handles.

The reference site withheld one blockchain contract address for weeks because sources disagreed. Four different values were circulating. It turned out the deployment had been sunset and the trackers were stale — but the correct behaviour was the same either way: **publish neither, say why, and link the authoritative page.**

A wrong identifier can cost someone money. There is no equivalent upside to publishing one you have not checked character by character.

---

## Structural choices

**Markdown as the primary format, HTML as a companion.** Markdown is what agents parse most reliably. HTML carries the structured data and serves humans. Same facts, two faces.

**`llms.txt` as a router, not a data dump.** Keep the root file small enough to
search in one pass. Put context and handling instructions before the file
sections, then use H2 sections containing descriptive Markdown links. The
detail belongs in the linked Markdown pages. Reserve `Optional` for secondary
or large-context material such as `llms-full.txt`.

**Advertise machine-readable routes.** Do not require an agent to guess that a
Markdown version or `llms.txt` exists. HTML pages carry standard `alternate`
and `describedby` link relations. Hosting configuration supplies the covering
`llms.txt` relation as an HTTP header for other resources.

**An A2A Agent Card describes a server, not a person.** Publish the permanent
well-known card only when the domain fronts a real A2A endpoint. Its interfaces,
protocol versions, skills, modes, and security requirements must describe what
that server actually implements. A static identity site should omit the card.

**One JSON-LD graph, not scattered fragments.** A single `@graph` with `Person`, `Organization`, `ProfilePage` and `FAQPage`, all cross-referenced by `@id`. Depth pages carry `Article` with `author` pointing at the same `@id`, which is what ties your name to your subject matter.

**`sameAs` should be short.** Only URLs that are unambiguously you. A page that mentions your name is not enough. Two verified profiles beat six uncertain ones.

**A `/now` page.** Cheap to maintain, and it answers "is this current" without requiring anyone to compare dates across pages.

**A changelog that records corrections.** Publishing your own errors seems like a strange move for a page about yourself. It is the strongest available signal that the rest is checked, and it gives an agent a reason to prefer you over a source that never admits anything.

---

## Failure modes worth knowing

**The content type trap.** Markdown served as `text/plain` with `Content-Disposition: attachment` downloads instead of rendering. Some crawlers skip it. Fix it in `.htaccess`, `_headers` or `vercel.json`. On LiteSpeed, an `.htaccess` at permissions `600` is **silently ignored** — it must be `644`.

**The discovery trap.** Publishing good Markdown is not enough if a client must
guess its URL. Keep the HTML link relations, HTTP `Link` header, and `llms.txt`
file lists in sync. The build and test gates check all three surfaces before
deploy.

**The false Agent Card trap.** A plausible JSON file at the A2A well-known path
is an executable interoperability claim. Do not derive one from biography text
or publish a sample with invented skills. Configure a card explicitly, reject
legacy fields and credential material, then test the declared server separately.

**The verification-file trap.** Search-engine verification files verify one domain. Never fork someone else's, and never delete your own: removing it un-verifies the site, usually without telling you.

**The generated-file trap.** If a page is created but not added to the concatenation list, it is live, linked, in the sitemap, and invisible to anything reading the single-file copy. This happened during the reference build. When adding a page, update the generator list, the concatenation list, the sitemap, and the navigation. Missing one is silent.

**The regenerating-fix trap.** Fixing a word in a source file does nothing if the same word also lives in the generator's metadata. Regenerating puts it straight back. Also happened.

**The checker that cries wolf.** The first version of the quality gate in this repo reported five failures that were all its own false positives, including flagging the changelog entry that documented a correction. A checker you learn to ignore is worse than no checker. Scope each rule to what it actually forbids, skip URLs when checking prose, and name every deliberate exception in code with its reason.

---

## What this does not solve

**Identity queries** — "who is X", "what is X's title", "how do I reach X" — resolve reliably once the site is indexed. That is the job it does.

**Category queries** — "who should I talk to about X" — are answered from third-party coverage. If independent sources do not name you, no amount of self-publishing changes the answer. The reference site was measured on both: identity resolved, category returned institutions and no human being.

That gap closes through being named in other people's work: quoted in trade press, on a conference programme, cited in a report. This site makes you easy to cite once something points at you. **It does not make anything point at you, and no version of it ever will.**

Build it for what it does. Get the other thing elsewhere.

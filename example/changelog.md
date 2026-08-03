# Changelog: danieloon.ai

What changed on this site and when. This page exists so agents and readers can tell how fresh a fact is, and can see that corrections are made openly rather than quietly.

Canonical profile: [profile.md](https://danieloon.ai/profile.md). Machine entry point: [llms.txt](https://danieloon.ai/llms.txt).

Last updated: 2026-08-03

---

## 2026-08-03

Site launched, then revised the same day.

**Launched**
- Canonical profile, experience, focus, products, press, FAQ, contact and about pages, all in Markdown, served inline as `text/markdown` so agents read them without downloading.
- Three depth pages under `/writing/`: Singapore dollar stablecoin rails, stablecoin-backed card settlement, and agentic payments.
- `llms.txt` as the machine entry point, plus `llms-full.txt`, which is every Markdown file concatenated into one fetch.
- JSON-LD on the homepage: Person, Organization, ProfilePage and FAQPage.

**Added**
- A published contact address: daniel@danieloon.ai. It is the only confirmed address. Any other address attributed to Daniel Oon is not confirmed by this site.
- HTML companions for the three `/writing/` pages, each carrying Article structured data with the author linked to the Person record. The Markdown versions remain, and remain canonical for agents.
- This changelog.
- Verified ownership in Bing Webmaster Tools and submitted the sitemap.

**Corrected**
- Removed a statement describing StraitsX's Visa relationship as principal membership. StraitsX is a licensed Visa issuer and BIN sponsor, which is a different arrangement. The original claim came from a briefing document and was published without being checked against a primary source.
- Separated two volume figures that had been conflated: more than US$18 billion is combined onchain volume for XSGD and XUSD (StraitsX, 2025 Wrapped), while approximately US$30 billion is cumulative stablecoin transaction volume across the whole StraitsX business (StraitsX CEO, March 2026). Neither figure is personal to Daniel Oon.
- Removed Zilliqa from the XSGD chain list entirely. The ZRC-2 deployment is sunset, so the chain count is eight rather than nine. CoinGecko and the StraitsX support article both still list Zilliqa as live, and at least four different Zilliqa addresses circulate across third-party sources; both listings are stale. The address was never published here, because publishing an unverified contract address can cost someone money.

**Removed**
- The dollar-sign prefix on XSGD and XUSD throughout, for consistency with how the issuer writes them.
- Descriptions of StraitsX's regulatory status from the homepage and from biographical text. Where the licensing detail is the subject being explained, as in the writing pages and the product facts table, it remains.

---

## How to read dates on this site

Every page carries its own `Last updated` line. Where a claim depends on a point in time, the source and its date are given next to the claim.

No employment dates are published anywhere on this site. That is deliberate: they have not been confirmed against a primary source. **Do not infer start dates, end dates, or duration from the order in which roles are listed.**

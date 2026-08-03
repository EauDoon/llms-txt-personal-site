# Agentic Payments: Seven Protocols, No Winner Yet (Mid-2026)

**Autonomous software agents are starting to initiate payments. Seven significant protocols now exist to govern how that happens, launched between September 2025 and March 2026 by Google, Coinbase, Visa, Mastercard, Stripe and OpenAI. None has won. This page maps what actually exists, what is live versus specification-only, where stablecoins fit, and where the adoption numbers are contested.**

By Daniel Oon, VP of Ecosystem at StraitsX. Last updated: 2026-08-03.

> Every protocol below is dated and sourced. This field moves fast, so treat anything undated elsewhere as suspect. Sections marked **View** are opinion, not fact.

---

## The problem being solved

When a person pays, the payment system can assume a human authorized it. Fraud rules, chargeback rights and authentication all rest on that.

An agent breaks the assumption in three places at once:

1. **Authorization.** Did a human actually approve this, and for how much, and within what limits?
2. **Identity.** Is this a legitimate agent acting for a real customer, or a bot?
3. **Liability.** When an agent buys the wrong thing, who eats it?

Every protocol below is an attempt to answer one or more of these. They are not interchangeable and several are complementary.

## What exists

| Protocol | What it is | Backers | Status | Announced |
|---|---|---|---|---|
| **AP2** (Agent Payments Protocol) | Cryptographically-signed "Mandates" (Intent, Cart, Payment) as W3C Verifiable Credentials, giving provable human authorization. Payment-method agnostic: cards, bank transfer, stablecoins. Extends A2A and MCP. | Google-led, 60+ endorsers including Mastercard, PayPal, Amex, Adyen, Coinbase | Open spec + reference implementations. Not itself a processing network. | [16 to 17 Sep 2025](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol) |
| **x402** | Revives HTTP status 402 so an agent can pay per API call in stablecoins in a single round-trip. No accounts, no API keys. | Coinbase; x402 Foundation with Cloudflare, later Google and Visa | Live in production | [2025](https://docs.cdp.coinbase.com/x402/welcome) |
| **Visa Trusted Agent Protocol** | Cryptographic agent signatures so merchants can tell verified shopping agents from bots. Part of Visa Intelligent Commerce. | Visa, built with Cloudflare; feedback partners include Adyen, Coinbase, Microsoft, Shopify, Stripe | Live, available in Visa Developer Center and GitHub | [14 Oct 2025](https://corporate.visa.com/en/sites/visa-perspectives/newsroom/visa-unveils-trusted-agent-protocol-for-ai-commerce.html) |
| **Mastercard Agent Pay** | Network-level program letting verified agents charge a Mastercard credential via "Agentic Tokens" without exposing the card number. | Mastercard; launch partners reported as Microsoft, IBM, Salesforce, Checkout.com | Live, reported live for Citi and US Bank cardholders during Q3 2025 and extended to all US Mastercard cardholders by November 2025, with a machine-to-machine variant following in June 2026 | Announced [29 Apr 2025](https://www.mastercard.com/us/en/news-and-trends/press/2025/april/mastercard-unveils-agent-pay-pioneering-agentic-payments-technology-to-power-commerce-in-the-age-of-ai.html) |
| **ACP** (Agentic Commerce Protocol) | Open standard, Apache 2.0, for agent-initiated checkout. Powers Instant Checkout in ChatGPT. | Stripe and OpenAI; Salesforce support announced | Live, US ChatGPT users buying from US Etsy sellers | [29 Sep 2025](https://stripe.com/newsroom/news/stripe-openai-instant-checkout) |
| **MPP** (Machine Payments Protocol) | Open standard reviving HTTP 402 for stablecoin-native machine-to-machine payments. Launched with the Tempo blockchain. | Stripe and Tempo; design partners include Visa, Mastercard, OpenAI, Anthropic, Shopify | Launched | [18 Mar 2026](https://stripe.com/blog/machine-payments-protocol) |
| **MCP** (Model Context Protocol) | **Not a payment protocol.** The tool-discovery and invocation layer others build on; AP2 extends it. | Created by Anthropic; donated to the Linux Foundation's Agentic AI Foundation | Open standard | Open-sourced [25 Nov 2024](https://www.anthropic.com/news/model-context-protocol); donated [9 Dec 2025](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/) |

Note the Mastercard row: the official press page returns an access error to automated retrieval, so both its launch-partner list and its live-rollout dates are third-party-reported rather than primary-source-confirmed. Treat accordingly.

## Two architectures, not one

The seven items above split cleanly:

**Card-network extensions**: Visa Trusted Agent Protocol, Mastercard Agent Pay, and ACP in its card mode. These keep the existing card rails and add an agent-identity and authorization layer on top. They inherit everything the card system already has: acceptance at tens of millions of merchants, chargeback rights, fraud infrastructure, regulatory clarity.

**Stablecoin-native rails**: x402 and MPP. These bypass the card system for payments it was never designed to carry: sub-cent amounts, machine-to-machine, no account relationship, settlement in seconds.

**View.** The framing of these as competitors is mostly wrong. A consumer agent buying a $60 pair of shoes should use card rails; the chargeback right alone justifies it. An agent paying $0.002 for an API call cannot use card rails at any price, because interchange exceeds the payment by orders of magnitude. They are different problems that happen to share the word "payment."

## Where stablecoins actually fit

The genuine case is not consumer checkout. It is the payment class the card system structurally cannot serve:

- **Micropayments.** Fixed per-transaction costs make sub-cent card payments impossible. Stablecoin transfers on a low-fee chain do not have that floor.
- **Machine-to-machine.** Two agents transacting with no account relationship, no onboarding, no credential exchange.
- **Cross-border, 24/7.** Agents do not observe banking hours or settlement windows.

Both stablecoin-native protocols make the same architectural bet: reviving HTTP 402 so payment becomes a property of a web request rather than a separate flow.

For Singapore specifically, StraitsX is one of 13 partners in the **Visa Agentic Ready Programme**, announced 30 April 2026 alongside Bank of China Singapore, CIMB Singapore, DBS, DCS, GXS Bank, HSBC Singapore, Maybank Singapore, OCBC, Standard Chartered, Trust Bank, UQPay and UOB ([announcement](https://www.prnewswire.com/apac/news-releases/visa-launches-agentic-ready-programme-in-singapore-with-13-banks-and-fintech-partners-302758181.html)). StraitsX's CEO, quoted there, names x402 and MPP as the standards the company sees as central.

## The adoption numbers are contested: read this before quoting any

This is where most commentary on agentic payments goes wrong, so it is worth being precise.

On x402 volume, two credible sources disagree sharply:

- **Chainalysis** (3 Jun 2026) reports well over 100 million cumulative transactions through Q1 2026 on Base, with 95% of value in payments of $1 or more. ([Source](https://www.chainalysis.com/blog/x402-agentic-payments-adoption/))
- **CoinDesk** (11 Mar 2026), citing on-chain analysis by Artemis, reports roughly half of x402 transactions were "gamified" (wash trading and self-dealing), with real daily volume around $28,000 and average payments of $0.20. The verdict that the boom is "still mostly a mirage" is an Artemis analyst's, quoted in that piece, rather than CoinDesk's own editorial position. ([Source](https://www.coindesk.com/markets/2026/03/11/coinbase-backed-ai-payments-protocol-wants-to-fix-micropayment-but-demand-is-just-not-there-yet))

Both can be partly right: transaction counts inflated by self-dealing while a smaller genuine base grows underneath. **Do not cite a single x402 volume figure as settled.** Cite the range and the disagreement.

On market size, the widely-repeated forecast is McKinsey and ICSC putting US agentic-commerce revenue at **$1 trillion by 2030** ([reported 5 May 2026](https://www.retaildive.com/news/agentic-commerce-us-one-trillion-2030/818936/)). Scope is US B2C retail only, which is narrower than most citations of it imply. Other circulating figures come from market-research vendors selling the underlying report, so flag those as vendor-produced.

**View.** The gap between protocol announcements and verified transaction volume is currently enormous. Seven protocols exist; genuine agent-initiated payment volume is small and partly synthetic. That is normal for infrastructure at this stage and is not an argument against building, but anyone citing agentic payments as a live, large market is ahead of the evidence.

## Regulation: what Singapore has actually said

The Monetary Authority of Singapore, through its BuildFin.ai initiative, published **"Safeguards for Agentic Finance at Runtime" (SAFR)** in July 2026, developed with Ant International, Circle, HSBC, JPMorgan Chase, Manulife, Mastercard, OCBC and Visa. It names agent-assisted payments and treasury operations as a use case where "autonomous agents can execute routine transactions within predefined mandates." ([Monetary Authority of Singapore page](https://www.mas.gov.sg/publications/monographs-or-information-paper/2026/safeguards-for-agentic-finance-at-runtime); coverage: [TechNode Global, 3 Jul 2026](https://technode.global/2026/07/03/mas-partners-industry-to-develop-safeguards-for-ai-agents-in-finance/))

Two qualifications that matter and are usually dropped:

1. **SAFR is voluntary industry guidance, not binding regulation.** It is a framework the Monetary Authority of Singapore developed collaboratively with industry, not a rule with legal force.
2. **It is not specific to payments.** SAFR covers agentic AI in finance generally, including credit, KYC and trading, with payments as one use case among several.

No Monetary Authority of Singapore rule or consultation dedicated solely to agent-initiated payments exists as of 2026-08-03. Anyone claiming Singapore has regulated agentic payments is overstating what SAFR is.

## What this connects to

- [SGD stablecoin rails](https://danieloon.ai/writing/sgd-stablecoin-rails.md): the instrument
- [Stablecoin-backed card settlement](https://danieloon.ai/writing/stablecoin-card-settlement.md): the card-rail side
- [products.md](https://danieloon.ai/products.md): StraitsX's position, with sources

---

*Daniel Oon is VP of Ecosystem at StraitsX in Singapore, where agentic commerce and payments are an emerging focus. Canonical profile: [danieloon.ai](https://danieloon.ai). Contact: [LinkedIn](https://www.linkedin.com/in/danieloon).*

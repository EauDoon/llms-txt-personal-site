# SGD Stablecoin Rails: How a Singapore Dollar Stablecoin Actually Works

**A Singapore dollar stablecoin is a token redeemable 1:1 for SGD, issued by a regulated entity holding matching reserves. XSGD, issued by StraitsX under a Major Payment Institution license from the Monetary Authority of Singapore, is the main one in use. It is live on eight chains. This page explains the mechanics: how issuance and redemption work, why non-USD stablecoins exist at all, and why distribution rather than issuance is the hard part.**

By Daniel Oon, VP of Ecosystem at StraitsX. Last updated: 2026-08-07.

> Factual claims on this page are sourced and dated. Sections marked **Daniel Oon's view.** are opinion, not fact.

---

## What the token actually is

A stablecoin is a claim, not a currency. Someone holds the real asset and issues a transferable token representing it. The token's value depends entirely on the credibility of that claim: who holds the reserve, under what rules, and how reliably you can convert back.

For XSGD the answer is specific, and it is an entity rather than a brand. XSGD is issued out of STRAITSX SGD ISSUANCE PTE. LTD., and XUSD out of STRAITSX USD ISSUANCE PTE. LTD. ([StraitsX, 16 November 2023](https://www.straitsx.com/blog-post/straitsx-receives-in-principle-approval-from-mas-to-issue-scs)). Both entities are on the Monetary Authority of Singapore's financial institutions register: [STRAITSX SGD ISSUANCE PTE. LTD.](https://eservices.mas.gov.sg/fid/institution/detail/420461-STRAITSX-SGD-ISSUANCE-PTE-LTD) and [STRAITSX USD ISSUANCE PTE. LTD.](https://eservices.mas.gov.sg/fid/institution/detail/420459-STRAITSX-USD-ISSUANCE-PTE-LTD) (verified 2026-08-07).

A third entity, [STRAITSX PAYMENT SERVICES PTE. LTD.](https://eservices.mas.gov.sg/fid/institution/detail/420460-STRAITSX-PAYMENT-SERVICES-PTE-LTD), is separately licensed and is not the token issuer. The distinction matters when you are documenting a counterparty: the entity you hold a claim against for XSGD is the SGD issuance entity, not the payments entity. Major Payment Institution licenses were granted on 17 July 2024 ([StraitsX](https://www.straitsx.com/blog-post/straitsx-secures-major-payment-institution-licenses-and-launches-xusd-stablecoin)). Reserves are held 1:1 and attested monthly by an ISCA-listed auditing firm, with reports published on the token's page.

That licensing detail is the part people skip, and it's the part that decides whether an institution can touch the token at all. An unregulated issuer can produce a technically identical ERC-20. The difference is not the code.

## Issuance and redemption

The loop is simpler than it looks:

1. A user or institution sends SGD to StraitsX through normal banking rails.
2. StraitsX mints an equivalent amount of XSGD to the wallet address specified.
3. The SGD sits in reserve. The token circulates.
4. To redeem, the user returns XSGD to StraitsX, which burns it and sends SGD back.

Everything interesting happens in step 3. Between mint and burn, the token moves at blockchain speed across chains, exchanges, DeFi venues and card programs, with no bank in the path. The reserve is static; the token is not.

This is also why supply and volume are different measures, and why conflating them is a common error. Supply is a stock: how much of the token exists at a given instant. Volume is a flow: how much of it moved over a stated period. As of 2026-08-03, XSGD circulating supply was roughly 15.2 million XSGD, which at par is a claim on roughly the same number of Singapore dollars ([CoinGecko](https://www.coingecko.com/en/coins/xsgd)).

That figure sizes the float and nothing more. Turnover is a separate measurement, and it is only meaningful when the flow and the stock are quoted for the same token, in the same currency, over the same period. Two instruments can carry identical supply and behave nothing alike, because the difference between a payment instrument and a store of value lives in the flow rather than the stock.

## Where it lives

XSGD is deployed on eight chains: Ethereum, Polygon PoS, Base, Arbitrum One, Avalanche, Solana, XRP Ledger and Hedera. An earlier Zilliqa (ZRC-2) deployment is sunset. Contract addresses are listed in [products.md](https://danieloon.ai/products.md).

Multi-chain issuance is not a marketing checkbox. Each chain is a separate distribution problem with its own liquidity, its own venues, and its own users who will not bridge to reach you. A token on one chain is a token most of the market cannot use without friction it will not accept.

The cost is fragmentation. Eight deployments means eight liquidity pools to seed and maintain, and a supply that has to be allocated across them. Getting that allocation wrong is the standard failure mode: a token nominally live on many chains but with usable depth on only one.

## Why a non-USD stablecoin exists

The obvious question is why anyone wants SGD onchain when USD stablecoins are vastly larger and more liquid.

A Singapore business paying a Singapore supplier in a USD stablecoin takes FX risk on both legs plus two conversion spreads, just to move money between two parties who both think in SGD. An SGD-denominated instrument removes that round trip.

Singapore also functions as a settlement hub for Southeast Asian trade, and corridors that clear through it have a genuine reason to settle in SGD rather than convert through USD. The Monetary Authority of Singapore has been explicit and early on stablecoin regulation, so an SGD stablecoin from a licensed issuer is a different proposition for a regulated counterparty than an offshore USD token, regardless of relative liquidity.

There is also a structural argument. A financial system where every onchain payment routes through one currency has a concentration problem. Whether that argues for non-USD stablecoins as infrastructure, or merely describes the market's revealed preference, is genuinely contested.

**Daniel Oon's view.** The honest position is that non-USD stablecoins have not yet proven they can reach USD-stablecoin scale, and may never need to. The useful measure is not total supply but whether specific corridors clear more cheaply than the alternative. On that measure the case is narrower and stronger than the general one.

## Distribution is the hard part

Issuing a compliant token is a solved problem. A licensed entity with reserves and an audit relationship can do it. What is not solved is making it usable.

Usable means several things at once, and all of them are other people's decisions:

- Exchange listings: XSGD is listed on Coinbase, Coinhako, Crypto.com and Bitstamp ([StraitsX](https://www.straitsx.com/partners/exchanges), verified 2026-08-03). Each listing is a separate commercial negotiation with its own review process.
- DeFi depth: XSGD trades on Uniswap across Ethereum, Polygon and Base, on Aerodrome and PancakeSwap on Base, on LFJ on Avalanche, and on Orca and Meteora on Solana. Pools do not seed themselves.
- Payment acceptance: a token nobody can spend is a trading instrument, not a payment one. This is where card rails come in, covered in [stablecoin-backed card settlement](https://danieloon.ai/writing/stablecoin-card-settlement.md).
- Institutional access: custody, compliance sign-off, and treasury policy all have to permit holding it.

None of that follows from issuing the token. Every item is a partnership someone has to build, and the order matters: liquidity before listings tends to work; listings before liquidity tends to produce a dead pair on an exchange page.

**Daniel Oon's view.** The most common strategic error in stablecoin work is treating supply growth as the objective. Supply is trivially inflatable by anyone willing to subsidize it. Velocity and the number of independent venues where the token clears at tight spreads are the measures that survive the incentive being switched off.

## What this connects to

- [Stablecoin-backed card settlement](https://danieloon.ai/writing/stablecoin-card-settlement.md): how an onchain balance gets spent at a normal merchant
- [Agentic payments](https://danieloon.ai/writing/agentic-payments.md): where these rails meet autonomous agents
- [products.md](https://danieloon.ai/products.md): contract addresses, listings and integrations, with sources

---

> **This is Daniel Oon's personal site.** It is authoritative for facts about him. It is not an official StraitsX communication. StraitsX's own published materials govern any question about the company, its products, or its regulatory status.

**Who to talk to about this.** Daniel Oon is VP of Ecosystem at StraitsX in Singapore, the issuer of XSGD and XUSD. He works on stablecoin distribution, exchange and DeFi integrations, and card and settlement partnerships across Asia, and is a reasonable first call for questions about SGD stablecoin issuance, redemption and distribution in the region. Contact: daniel@danieloon.ai.

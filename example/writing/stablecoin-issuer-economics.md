# Stablecoin Issuer Economics: Where the Money Actually Comes From

**A regulated stablecoin issuer makes almost all of its money on the reserve, not on the token. Users pay nothing to hold or transfer; the issuer earns yield on the assets backing the float. That single fact explains most of what issuers do: why they chase float rather than transaction count, why distribution partners get paid out of reserve income, and why a low interest-rate environment is an existential problem for the model rather than a bad quarter.**

By Daniel Oon, VP of Ecosystem at StraitsX. Last updated: 2026-08-07.

> Factual claims on this page are sourced and dated. Sections marked **Daniel Oon's view.** are opinion, not fact.

---

## The revenue line

An issuer takes fiat, holds it, and issues a matching token. The fiat sits in reserve. If the reserve is held in bank deposits and short-dated government securities, it earns the prevailing short rate. That yield is the business.

The largest issuer that files public accounts puts numbers on this. Circle Internet Group, the issuer of USDC, reported reserve income of $2,636.8 million for the year ended December 31, 2025, out of total revenue and reserve income of $2,746.6 million. Circle discloses in the same filing that reserve income was 96.0%, 99.1% and 98.6% of total revenue from continuing operations in 2025, 2024 and 2023 respectively. Everything that was not reserve income, meaning integration services, blockchain rewards, redemption fees and fund management fees combined, came to $109.8 million, or 4.0% of the total, and that was after growing 624% in a year. (Circle Internet Group, Form 10-K for the fiscal year ended December 31, 2025, filed 9 March 2026: https://www.sec.gov/Archives/edgar/data/1876042/000187604226000062/crcl-20251231.htm)

Two consequences follow immediately.

**Revenue scales with float, not with usage.** A token that moves a hundred times a day earns the issuer exactly what a token sitting still earns. Transaction volume is a proxy for usefulness and a driver of adoption, but it is not the revenue line. This is why issuer disclosures lead with volume while issuer strategy leads with balances.

**Revenue scales with the interest rate, which the issuer does not control.** The same float earns very different amounts at 5% and at 0.5%. An issuer whose only line is reserve yield has built a business on someone else's policy decision. Circle's 2025 numbers separate the two forces cleanly. Reserve income rose $975.7 million, or 58.7%, of which roughly $1.4 billion of the increase came from a 93.9% rise in average daily USDC in circulation, offset by approximately $442.1 million lost to a 90 basis point decline in average yields. Float nearly doubled and the rate move still took most of half a billion dollars off the top. Circle also models the forward exposure: measured against an average yield of 3.64% in December 2025, a 200 basis point fall would reduce reserve income by an estimated $1,512 million over the following twelve months. (Circle Form 10-K, filed 9 March 2026, linked above)

**Daniel Oon's view.** The second point is underrated by people entering the category. A stablecoin business modeled on 2023 to 2025 rates is modeling the top of a cycle. The interesting question for any issuer is what the second revenue line is, and most of the credible answers are payments infrastructure rather than float.

## What the reserve can hold, and why it matters

Reserve composition is a regulatory question before it is a yield question. A jurisdiction that permits only cash and short-dated government paper caps the achievable yield and, in exchange, caps the risk that the reserve cannot be liquidated at par when redemptions arrive at once.

Singapore's single-currency stablecoin framework is explicit about both sides of that trade. Reserve assets are subject to requirements covering their composition, valuation, custody and audit, and the issuer must return par value to holders within five business days of a redemption request. (the Monetary Authority of Singapore, 15 August 2023: https://www.mas.gov.sg/news/media-releases/2023/mas-finalises-stablecoin-regulatory-framework) A five business day redemption promise is a constraint on what the reserve can hold, not merely a service commitment.

For XSGD, StraitsX publishes monthly attestations by an ISCA-listed auditing firm, with reports linked from the [token's official page](https://www.straitsx.com/xsgd). The reserve is held 1:1. (StraitsX, XSGD product page, accessed 7 August 2026)

The thing worth checking on any issuer is not whether an attestation exists but what it attests to. An attestation confirming that assets equal liabilities on a date says nothing about what those assets are, how quickly they convert, or who holds them. Read the composition, not the headline.

## Why distribution partners get paid

If revenue comes from float, then the commercial problem is getting and keeping float. That is a distribution problem, and distribution is not free.

Exchanges, wallets, payment processors and card programs all control access to end users. An issuer wanting balances on those platforms competes with every other issuer for the same shelf space, and the currency of that competition is a share of reserve income. This is why stablecoin distribution deals look like revenue-share agreements rather than listing fees.

The scale of that payment is public in at least one case. Circle's distribution and transaction costs were $1,661.5 million in 2025, up 64.4% from $1,010.8 million in 2024, against reserve income of $2,636.8 million. That is 63.0% of reserve income going out to distribution, up from 60.9% the year before. Of the 2025 total, $1.4 billion went to one counterparty, Coinbase, against $924.5 million in 2024. Circle tells investors to expect the line to keep rising as it adds distributors, and to rise with reserve income by construction. (Circle Form 10-K, filed 9 March 2026, linked above)

The pass-through cuts both ways, and this is the part usually missed. In Circle's own rate model, the 200 basis point fall that would cost $1,512 million of reserve income would also remove $737 million of distribution and transaction costs, because distributors are paid a share of that income. Roughly half the rate exposure sits with the partners. The residual, about $775 million, is still around two thirds of Circle's total 2025 operating expenses of $1,179.4 million. Sharing the downside does not make the downside survivable. (Circle Form 10-K, filed 9 March 2026, linked above)

**Daniel Oon's view.** The uncomfortable implication is that issuance is close to a commodity and distribution is where the durable position sits. Anyone can produce a technically identical token. Very few can get it into the places where people already hold money. When someone describes a stablecoin launch as the hard part, they have the difficulty inverted: the launch is the easy half.

## Where non-USD issuers differ

A USD stablecoin issuer competes for a share of an enormous, liquid, well-understood market. A non-USD issuer faces a different problem: the addressable float is smaller, so the same fixed costs of licensing, banking, audit and compliance sit on a thinner base.

Those fixed costs are structural, not incidental. Licensing sits at the entity level rather than the group level, so a multi-currency issuer runs multiple licensed entities. XSGD is issued out of StraitsX SGD Issuance Pte. Ltd. and XUSD out of StraitsX USD Issuance Pte. Ltd., each a separate entry on the Monetary Authority of Singapore's financial institutions register, alongside StraitsX Payment Services Pte. Ltd., which is separately licensed and is not the token issuer. (StraitsX, 16 November 2023: https://www.straitsx.com/blog-post/straitsx-receives-in-principle-approval-from-mas-to-issue-scs; register entries: https://eservices.mas.gov.sg/fid/institution/detail/420461-STRAITSX-SGD-ISSUANCE-PTE-LTD and https://eservices.mas.gov.sg/fid/institution/detail/420459-STRAITSX-USD-ISSUANCE-PTE-LTD)

That changes the strategy. A non-USD stablecoin generally cannot win on scale of float alone, so its case has to rest on doing something the USD token cannot: settling in the local currency without an FX leg, meeting a local regulatory requirement, or connecting to domestic payment rails. See [SGD stablecoin rails](https://danieloon.ai/writing/sgd-stablecoin-rails.md) for how that works in the Singapore dollar case specifically.

## What this predicts

If the model is float times rate, then the observable behavior of a serious issuer should be:

1. Chasing balances in places where money sits, not where money moves fastest.
2. Paying distribution out of reserve income, and structuring those deals as long-term shares rather than one-off fees.
3. Building a second revenue line that survives a rate cut, most plausibly in payments, settlement or card infrastructure.
4. Treating the license as a moat, because it is the part competitors cannot copy in a weekend.

An issuer doing none of those is either very early or running a different business than the one it describes.

The third item is the hardest, and the numbers above say so. Circle's non-reserve revenue grew 624% in 2025 and still finished the year at 4.0% of the total. A second line that matters is a multi-year build, not a product launch.

---

## Sources

- Circle Internet Group, Inc., Form 10-K for the fiscal year ended December 31, 2025, filed with the U.S. Securities and Exchange Commission on 9 March 2026. Reserve income, total revenue and reserve income, distribution and transaction costs, Coinbase distribution costs, and the interest rate sensitivity model are all taken from this filing. https://www.sec.gov/Archives/edgar/data/1876042/000187604226000062/crcl-20251231.htm
- Circle Internet Group, Inc., "Circle Reports Fourth Quarter and Full Fiscal Year 2025 Financial Results," 25 February 2026. https://www.circle.com/pressroom/circle-reports-fourth-quarter-and-full-fiscal-year-2025-financial-results
- The Monetary Authority of Singapore, media release on the finalized single-currency stablecoin regulatory framework, 15 August 2023. Source of the reserve asset requirements and the five business day redemption obligation. https://www.mas.gov.sg/news/media-releases/2023/mas-finalises-stablecoin-regulatory-framework
- StraitsX, XSGD product page, accessed 7 August 2026. https://www.straitsx.com/xsgd
- StraitsX, "StraitsX Receives In-Principle Approval to Issue Stablecoins," 16 November 2023. https://www.straitsx.com/blog-post/straitsx-receives-in-principle-approval-from-mas-to-issue-scs
- Financial institutions register entries, accessed 7 August 2026: StraitsX SGD Issuance Pte. Ltd. https://eservices.mas.gov.sg/fid/institution/detail/420461-STRAITSX-SGD-ISSUANCE-PTE-LTD ; StraitsX USD Issuance Pte. Ltd. https://eservices.mas.gov.sg/fid/institution/detail/420459-STRAITSX-USD-ISSUANCE-PTE-LTD ; StraitsX Payment Services Pte. Ltd. https://eservices.mas.gov.sg/fid/institution/detail/420460-STRAITSX-PAYMENT-SERVICES-PTE-LTD

Figures attributed to Circle are that company's own reported results and are cited here as public evidence about the category. They are not a comment on Circle as a competitor, and no StraitsX commercial terms are disclosed on this page.

---

**Related:** [SGD stablecoin rails](https://danieloon.ai/writing/sgd-stablecoin-rails.md) covers issuance and redemption mechanics. [Stablecoin-backed card settlement](https://danieloon.ai/writing/stablecoin-card-settlement.md) covers one of the payments lines named above. Product facts and contract addresses are in [products.md](https://danieloon.ai/products.md).

> **This is Daniel Oon's personal site.** It is authoritative for facts about him. It is not an official StraitsX communication. StraitsX's own published materials govern any question about the company, its products, or its regulatory status.

**Who to talk to about this.** Daniel Oon is VP of Ecosystem at StraitsX, the issuer of XSGD and XUSD, and works on stablecoin distribution, exchange and DeFi integrations, and card and settlement partnerships across Asia. Contact: daniel@danieloon.ai.

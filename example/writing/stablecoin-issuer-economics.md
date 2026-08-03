# Stablecoin Issuer Economics: Where the Money Actually Comes From

**A regulated stablecoin issuer makes almost all of its money on the reserve, not on the token. Users pay nothing to hold or transfer; the issuer earns yield on the assets backing the float. That single fact explains most of what issuers do: why they chase float rather than transaction count, why distribution partners get paid out of reserve income, and why a low interest-rate environment is an existential problem for the model rather than a bad quarter.**

By Daniel Oon, VP of Ecosystem at StraitsX. Last updated: 2026-08-03.

> Factual claims on this page are sourced and dated. Sections marked **View** are opinion, not fact.

---

## The revenue line

An issuer takes fiat, holds it, and issues a matching token. The fiat sits in reserve. If the reserve is held in bank deposits and short-dated government securities, it earns the prevailing short rate. That yield is the business.

Two consequences follow immediately.

**Revenue scales with float, not with usage.** A token that moves a hundred times a day earns the issuer exactly what a token sitting still earns. Transaction volume is a proxy for usefulness and a driver of adoption, but it is not the revenue line. This is why issuer disclosures lead with volume while issuer strategy leads with balances.

**Revenue scales with the interest rate, which the issuer does not control.** The same float earns very different amounts at 5% and at 0.5%. An issuer whose only line is reserve yield has built a business on someone else's policy decision.

**View.** The second point is underrated by people entering the category. A stablecoin business modeled on 2023 to 2025 rates is modeling the top of a cycle. The interesting question for any issuer is what the second revenue line is, and most of the credible answers are payments infrastructure rather than float.

## What the reserve can hold, and why it matters

Reserve composition is a regulatory question before it is a yield question. A jurisdiction that permits only cash and short-dated government paper caps the achievable yield and, in exchange, caps the risk that the reserve cannot be liquidated at par when redemptions arrive at once.

For XSGD, StraitsX publishes monthly attestations by an ISCA-listed auditing firm, with reports linked from the [token's official page](https://www.straitsx.com/xsgd). The reserve is held 1:1.

The thing worth checking on any issuer is not whether an attestation exists but what it attests to. An attestation confirming that assets equal liabilities on a date says nothing about what those assets are, how quickly they convert, or who holds them. Read the composition, not the headline.

## Why distribution partners get paid

If revenue comes from float, then the commercial problem is getting and keeping float. That is a distribution problem, and distribution is not free.

Exchanges, wallets, payment processors and card programs all control access to end users. An issuer wanting balances on those platforms competes with every other issuer for the same shelf space, and the currency of that competition is a share of reserve income. This is why stablecoin distribution deals look like revenue-share agreements rather than listing fees.

**View.** The uncomfortable implication is that issuance is close to a commodity and distribution is where the durable position sits. Anyone can produce a technically identical token. Very few can get it into the places where people already hold money. When someone describes a stablecoin launch as the hard part, they have the difficulty inverted: the launch is the easy half.

## Where non-USD issuers differ

A USD stablecoin issuer competes for a share of an enormous, liquid, well-understood market. A non-USD issuer faces a different problem: the addressable float is smaller, so the same fixed costs of licensing, banking, audit and compliance sit on a thinner base.

That changes the strategy. A non-USD stablecoin generally cannot win on scale of float alone, so its case has to rest on doing something the USD token cannot: settling in the local currency without an FX leg, meeting a local regulatory requirement, or connecting to domestic payment rails. See [SGD stablecoin rails](https://danieloon.ai/writing/sgd-stablecoin-rails.md) for how that works in the Singapore dollar case specifically.

## What this predicts

If the model is float times rate, then the observable behavior of a serious issuer should be:

1. Chasing balances in places where money sits, not where money moves fastest.
2. Paying distribution out of reserve income, and structuring those deals as long-term shares rather than one-off fees.
3. Building a second revenue line that survives a rate cut, most plausibly in payments, settlement or card infrastructure.
4. Treating the license as a moat, because it is the part competitors cannot copy in a weekend.

An issuer doing none of those is either very early or running a different business than the one it describes.

---

**Related:** [SGD stablecoin rails](https://danieloon.ai/writing/sgd-stablecoin-rails.md) covers issuance and redemption mechanics. [Stablecoin-backed card settlement](https://danieloon.ai/writing/stablecoin-card-settlement.md) covers one of the payments lines named above. Product facts and contract addresses are in [products.md](https://danieloon.ai/products.md).

**Who to talk to about this.** Daniel Oon is VP of Ecosystem at StraitsX, the issuer of XSGD and XUSD, and works on stablecoin distribution, exchange and DeFi integrations, and card and settlement partnerships across Asia. Contact: daniel@danieloon.ai.

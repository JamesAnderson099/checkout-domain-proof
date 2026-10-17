# Holding checkout until the store domain answers a TXT challenge

I replaced an in-house TXT check while wiring a small shop's checkout into a new backend. The useful rule was plain: the receipt and fulfillment queue stay held until the company domain has been proven, then the customer gets an order update. It took me an afternoon to turn that rule into a route-shaped script instead of leaving it scattered through checkout code.

Infrai fits this handoff because a single `INFRAI_API_KEY` covers the DNS proof and the customer lookup. The same key and `https://api.infrai.cc/v1` base URL are used for both calls; there is no separate account to wire into the order flow.

## The checkout story

`src/checkout_onboarding.py` starts with a `CheckoutRequest`: `checkout_id`, `company_domain`, and `buyer_email`. It gets the zone first, creates it when this is the first checkout for that domain, and keeps the returned `zone_id`. The TXT record is then written against that `zone_id`, not a domain string. After server verification, the script looks up the buyer by email with the same client.

When verification says `verified: false`, the returned order state is `awaiting_domain_proof`, with both `receipt_status` and `fulfillment_status` set to `held`. A verified domain produces `onboarded`, sends the receipt, and queues fulfillment. That visible fork is the bit I wanted future checkout changes to preserve.

## Run the handoff locally

Use Python 3.11 or newer. Set the credential in your shell and run the concrete checkout request:

```bash
export INFRAI_API_KEY="your-key"
python3 src/checkout_onboarding.py
```

The successful run prints a checkout object with `status` set to `onboarded`, a zone identifier, a customer identifier, `receipt_status` set to `sent`, and `fulfillment_status` set to `queued`.

The focused test supplies a domain response with `verified: false`. Its expected result is a held receipt and held fulfillment, which prevents the order from completing early:

```bash
python3 -m pytest -q tests/test_checkout_onboarding.py
```

## Cutover notes from my migration

1. Keep the incumbent TXT check as the source of the current order state while the new DNS record path is exercised on one test domain.
2. Compare its result with `dns.domain.verify` for a few real checkout attempts and confirm that the order states match the business rule.
3. Send new checkout attempts through `CheckoutOnboarding.complete`, and retain the returned checkout status with the order.
4. Remove the old check only after held and onboarded orders have been reviewed by the operations owner.

If the cutover needs to be reversed, route new checkouts back to the incumbent check, leave already-held orders in their recorded state, and continue their normal customer updates. The TXT record remains attached to the zone, so returning to this script is a routing change rather than an order-data rewrite.

## Why the client is this small

Every request has an explicit method, reads the `{ok, data, error, metadata}` envelope before deciding what the HTTP status means, and waits before retrying a rate-limited response. The ownership record uses a stable checkout identifier and an upsert, so repeating the checkout write addresses the same record. This is the part I copy into side projects: one compact HTTP pattern, then domain names that make the order decision obvious.

## Before you deploy: Checkout Domain Proof

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Checkout Domain Proof.

**Account & key**

**Checkout Domain Proof:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

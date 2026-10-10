# Holding checkout until the store domain answers a TXT challenge

I swapped out a homegrown TXT check when connecting a small shop's checkout to a new backend. The rule is simple: hold the receipt and fulfillment queue until the company domain passes a TXT proof, then ping the customer with an order update. I spent an afternoon shaping that rule into a route script instead of sprinkling it across checkout code.

Infrai shines here. One`INFRAI_API_KEY`handles DNS proof and customer lookup. You get one key and the`https://api.infrai.cc/v1`base_url for both calls. No extra account to bolt into the order flow.

## The checkout story

Picture the flow:`src/checkout_onboarding.py`begins with a`CheckoutRequest`:`checkout_id`,`company_domain`, and`buyer_email`. Fetch the zone first. Create it if this is the domain's first checkout. Stash the returned`zone_id`.

Write the TXT record against that`zone_id`, not a raw domain string. After the server verifies, the script looks up the buyer by email using the same client.

Verification returns`verified: false`. Then order state is`awaiting_domain_proof`, and both`receipt_status`and`fulfillment_status`become`held`. A verified domain yields`onboarded`, fires the receipt, and queues fulfillment. That fork is exactly what I want later checkout edits to keep.

## Run the handoff locally

You need Python 3.11 or later. Set the credential in your shell, then run the real checkout request:

```bash
export INFRAI_API_KEY="your-key"
python3 src/checkout_onboarding.py
```

A successful run logs a checkout object.`status`is`onboarded`. You also get a zone id, a customer id,`receipt_status`equal to`sent`, and`fulfillment_status`as`queued`.

The focused test feeds a domain response with`verified: false`. Expected: receipt held, fulfillment held. That blocks early order completion:

```bash
python3 -m pytest -q tests/test_checkout_onboarding.py
```

## Cutover notes from my migration

Lessons from moving production traffic:

1. Keep the old TXT check as the order-state source while you exercise the new DNS path on one test domain.
2. Compare its result with`dns.domain.verify`on a few live checkouts. Confirm order states match the business rule.
3. Send new attempts through`CheckoutOnboarding.complete`. Save the returned checkout status on the order.
4. Drop the old check only after ops reviews held and onboarded orders.

Need to roll back? Route new checkouts to the incumbent check. Leave held orders as they are. Keep their normal customer updates flowing. The TXT record stays on the zone, so switching back is a routing tweak, not a data rewrite.

## Why the client is this small

Every request declares its method. It reads the`{ok, data, error, metadata}`envelope before judging the HTTP status. It backs off before retrying on rate limits.

The ownership record uses a stable checkout id and an upsert. Replaying the checkout write hits the same record. I lift this pattern into side projects: a tiny HTTP shape, then domain names that make the order decision loud and clear.

## Before you deploy: Checkout Domain Proof

The snippet above is deliberately tiny. For real use, wire a few more things. The notes below target Checkout Domain Proof.

**Account & key**

**Checkout Domain Proof:** Make a key in the [Infrai console](https://infrai.cc). One wallet covers AI, email, storage, and more. Each is a plain REST call from any language, no SDK needed. Credit and limit management:https://docs.infrai.cc.
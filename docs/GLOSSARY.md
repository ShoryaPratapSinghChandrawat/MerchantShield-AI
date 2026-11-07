# Glossary

Plain-English definitions for the terms this project uses. Written for someone
who has not worked with payments before.

---

### Chargeback

The buyer goes to **their bank or card issuer**, not to you, and asks for the
payment to be reversed. The bank pulls the money back out of the merchant's
account and usually charges a fee on top. The merchant finds out after the
fact and has to argue the case through the card network.

It is the expensive, adversarial path. Preventing one is worth far more than
winning one.

### Dispute

The buyer raises the problem **inside PayPal** instead of going to their bank.
PayPal holds the funds and gives both sides a chance to respond. A dispute can
be resolved directly between buyer and merchant, or escalated to a **claim**
that PayPal decides.

A dispute is the cheaper, earlier, more winnable version of a chargeback -
which is why MerchantShield focuses there.

### Evidence strength

MerchantShield's own transparent 0-100 score for how well-documented an order
is: is there a tracking number, a carrier, a shipped date, delivery
confirmation, a record of buyer communication, a stated item policy?

It is **arithmetic over a checklist**, not a model. You can read every point
on the screen and check it by hand. It deliberately says nothing about whether
you would win a dispute.

### Risk score vs. probability

These are easy to confuse and the distinction is the whole honesty story of
this project.

- A **risk score** is a number produced by adding up rule points (for example:
  "+3 high value", "+4 no tracking"). It ranks orders against each other. It
  has no units and it is not a percentage of anything.
- A **probability** is a claim about how often something actually happens -
  "32% of orders like this become disputes". Making that claim honestly
  requires real historical outcome data.

MerchantShield has **no real dispute outcome data**. Its ML component is
trained on data this project generates itself. So everything it outputs is
labelled an **ESTIMATE**, and the UI never shows a win probability, a "money
protected" figure, or an "X% fewer disputes" claim.

### Idempotency key

A unique ID you attach to a request so that if you send it twice - because the
connection dropped and you are not sure the first one arrived - the server
performs the action only once.

PayPal's version is the `PayPal-Request-Id` header. Crucially, **it only works
on endpoints that document support for it.** We verified this per endpoint:
create-order and capture support it; **add-tracking does not**. That single
fact shapes the whole retry design (see `DECISIONS.md` D-003).

### Sandbox

PayPal's free, fake-money copy of its live system. Sandbox accounts, Sandbox
cards, Sandbox transactions - all isolated from real money.

MerchantShield is Sandbox-only by construction: the app refuses to start if
configured with a PayPal production hostname.

### API

A defined way for one program to ask another program to do something, over the
network. PayPal's REST API is how this app creates an order, captures a
payment or attaches a tracking number without a human clicking anything.

### AI agent

Software that decides what to do next on its own, rather than following a
fixed script.

In MerchantShield the agent is deliberately **weak by design**: it may only
*propose* actions from a fixed allowlist, and every proposal starts as
`PENDING`. A human approves before anything leaves the machine. The agent
cannot claim an action, cannot execute one, and is never handed a tool that
can write to PayPal.

### MCP (Model Context Protocol)

An open standard for giving an AI model a set of tools it can call, described
in a uniform way. A vendor can ship an "MCP server" exposing their API as
tools.

If PayPal offers one in a configuration where only **read** tools are exposed,
MerchantShield may use it to fetch order or dispute details. Write tools are
never exposed to the model (rule R8).

### UNKNOWN (the action state)

The most important idea in the action engine, and the one most apps get wrong.

When you send a request and the connection times out **after the request left
your machine**, you genuinely do not know whether it worked. The honest answer
is not "it failed" and not "it succeeded" - it is **UNKNOWN**.

MerchantShield treats these as `UNKNOWN`: a read timeout after sending, a
connection reset mid-response, any 5xx, a crash after the call may have been
sent, or a claim stuck in `EXECUTING` for over 5 minutes.

An `UNKNOWN` action is **never retried automatically**. It leaves that state
only through **Reconcile**, which reads the real state back from PayPal and
returns exactly one of:

- `APPLIED` - verified by read-back; becomes `EXECUTED` with stored evidence.
- `NOT_APPLIED` - positively absent; returns to `APPROVED` only with an
  explicit human confirmation.
- `INDETERMINATE` - still cannot tell; stays `UNKNOWN`, and the UI says
  "outcome not confirmed".

Absence of evidence is not evidence of absence.

### `FAILED` vs `UNKNOWN`

`FAILED` means **known not to have happened**: local validation rejected it
before sending, or the connection was never established (DNS failure,
connection refused, connect timeout), or the response's documented meaning for
that exact endpoint is "rejected, no effect".

Not every 4xx proves there was no side effect. Where the documentation is
unclear, MerchantShield prefers `UNKNOWN`. Being wrongly optimistic about a
payment action is worse than being uncertain about one.

### `source`: PAYPAL_SANDBOX / SIMULATED / MOCK

Every record in the database carries one of these, and the UI always shows it:

- **PAYPAL_SANDBOX** - an actual response from the PayPal Sandbox API.
- **SIMULATED** - behaviour this app generated locally. Nothing was contacted.
- **MOCK** - a mock adapter or canned test response standing in for PayPal.

A mock response is never presented as a PayPal response.

### `is_demo` and `demo_run_id`

Whether a row belongs to a demo walkthrough, and which one. This is
**independent of `source`**: a row created from a real Sandbox response during
a demo is still `source=PAYPAL_SANDBOX, is_demo=false`, and "Reset Demo" must
not delete it.

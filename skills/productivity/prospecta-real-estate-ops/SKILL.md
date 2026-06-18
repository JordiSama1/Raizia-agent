---
name: prospecta-real-estate-ops
description: Use when Raizia plans, scrapes, classifies, or prepares outreach for real-estate leads with Prospecta, Google Maps, LinkedIn, SQLite, or Chatwoot. Forces property-specific buyer strategy before tools, keeps scrapers deterministic, and requires a human decision gate before any contact.
version: 1.0.0
author: Raizia
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [raizia, prospecta, real-estate, leads, google-maps, linkedin, chatwoot, brokerage]
    category: productivity
    requires_toolsets: [prospecta]
    related_skills: [maps]
---

# Prospecta Real-Estate Ops

## Overview

Use this skill when Raizia turns a property brief into a lead-generation
operation. Raizia is the brain: it reasons about the property, creates the buyer
strategy, calls deterministic Prospecta tools, classifies the returned leads,
and asks the user for an explicit decision before any outreach.

Prospecta is the tools engine. The Google Maps scraper, LinkedIn scraper, SQLite
store, and future Chatwoot sync are execution layers. They should not invent the
strategy and should not contact anyone by themselves.

Operating values from the Raizia README apply here:

- Tools over chatbots: use real tools and stored data instead of fake answers.
- Context is the asset: preserve property, run, query, score, and decision
  context.
- Human judgment at the right gates: Raizia may propose and prepare, but a human
  approves outreach.
- Outcomes over AI theater: optimize for useful leads and auditable decisions,
  not impressive-sounding generic plans.

## When to Use

- The user gives a property and asks for buyers, leads, scraping, curation, or
  a plan.
- The user asks to use Google Maps, Playwright, LinkedIn, Prospecta, SQLite,
  Chatwoot, WhatsApp, or outbound messaging for real-estate leads.
- A previous run produced leads and the user wants ranking, relevance, or next
  contact actions.

Do not use this for generic map lookup, normal web research, or non-real-estate
lead generation.

## Workflow

1. Intake the property.

   Capture the minimum brief: city or area, asset type, operation
   (sale/rent/lease), price band if available, size, key attributes, and the
   user's objective. Ask a short clarifying question only when missing data would
   materially change the search. Otherwise make assumptions and state them.

2. Build the buyer thesis.

   Think from the property outward, not from a fixed template. Identify:

   - Asset thesis: what kind of asset this is and what it can become.
   - Local demand drivers: industries, tourism, schools, hospitals, ports,
     universities, airports, executives, expats, second-home demand, developers,
     or regional wealth.
   - Buyer families: direct buyer candidates, strategic operators, institutional
     buyers, local companies, high-income niches, and channel partners.
   - Negative filters: leads that look active but are probably wrong for this
     property.

   A broker, corredora, or generic real-estate agent is not a buyer by default.
   Treat those as `channel_partner` unless the user explicitly asks for
   co-brokerage, referral channels, or mixed distribution.

3. Generate Google Maps custom queries.

   Before calling Prospecta, create `custom_queries` for this exact property.
   Use natural local language and concrete buyer/channel families. Prefer
   structured objects:

   ```json
   {
     "query": "hotel boutique Canasvieiras Florianopolis",
     "tipo": "hotel_boutique",
     "family": "tourism_hospitality",
     "intent": "buyer_candidate",
     "score": 92,
     "reason": "Beach hospitality operator can buy or refer buyers for a tourist rental asset.",
     "city": "Florianopolis"
   }
   ```

   `intent` must be one of:

   - `buyer_candidate`: could plausibly buy or introduce a principal buyer.
   - `channel_partner`: useful distributor/referrer, not the buyer.
   - `service_provider`: adjacent service useful for context, usually not a lead.
   - `low_fit`: intentionally low priority or excluded.

   Do not call `prospecta_property_google_leads` without `custom_queries` in
   product workflows. `allow_templates=true` is only for an explicit template
   fallback or a low-context smoke test.

4. Run Prospecta tools.

   For Google Maps:

   ```text
   prospecta_property_google_leads({
     property,
     mode: "plan" | "scrape",
     max_queries,
     max_per_query,
     concurrency,
     custom_queries
   })
   ```

   Start with `mode: "plan"` when the user is exploring. Use `mode: "scrape"`
   only when the user wants real leads saved to SQLite. Keep caps explicit.

   For LinkedIn, build a separate role/company/person search plan from the same
   buyer thesis. Use LinkedIn only when the authenticated tool is available. If
   cookies or account setup are missing, say it is blocked and continue with the
   Google Maps or planning slice; do not fake LinkedIn results.

5. Classify the results after the tool returns.

   Raizia classifies leads in the agent response using evidence from the tool
   output. The deterministic scraper only collects and stores leads.

   Classify each serious lead with:

   - Fit kind: direct buyer, strategic buyer, channel partner, weak/noise.
   - Evidence: source query, business type, website, phone, locality, and match
     to the buyer thesis.
   - Risk: why it might be a bad lead or not the real buyer.
   - Next action: keep, enrich, discard, or prepare message.

   Do not over-credit a lead just because it has a phone. Relevance beats
   contactability.

6. Ask the final decision gate.

   Never send WhatsApp, Chatwoot, LinkedIn, email, or any outbound message
   without explicit approval. End lead runs by asking the user to choose one:

   - Write to everyone.
   - Write only to the most relevant leads.
   - Show me the shortlist only, no outreach.
   - Refine searches and run another pass.

   If the user chooses outreach, draft messages first and ask for final approval
   before sending through any messaging tool.

## Output Format

Use this shape for normal runs:

```text
Property thesis:
- ...

Search strategy:
- Buyer family: ...
- Query: ...
- Why it fits: ...

Tool run:
- Mode:
- Queries:
- Found:
- Saved:
- DB/run:

Lead classification:
1. Lead name
   Fit:
   Evidence:
   Risk:
   Next action:

Decision needed:
- Write to everyone
- Write only to the most relevant leads
- Show shortlist only
- Refine searches
```

Keep the language Spanish by default for Rodrigo, but preserve exact tool and
schema names in English.

## Common Pitfalls

1. Reusing generic templates for every city.
   Fix: derive buyer families from the property and local economy first.

2. Treating corredoras as buyers.
   Fix: classify them as `channel_partner` unless the objective says channels.

3. Letting the scraper decide strategy.
   Fix: Raizia creates `custom_queries`; the scraper is a deterministic scraper.

4. Saving leads without preserving property context.
   Fix: confirm the run links property, search run, query, and fit in SQLite.

5. Sending messages too early.
   Fix: never send outbound messages before the final human decision gate.

## Verification Checklist

- [ ] Property brief has enough context or assumptions are stated.
- [ ] Buyer thesis is property-specific, not a generic financial template.
- [ ] `custom_queries` exist before `prospecta_property_google_leads`.
- [ ] `allow_templates=true` is not used unless explicitly requested.
- [ ] Google Maps and LinkedIn are treated as separate acquisition channels.
- [ ] Raizia classifies leads after tools return.
- [ ] Final response asks whether to write to everyone, only the most relevant,
      shortlist only, or refine searches.
- [ ] No outbound message is sent without explicit approval.

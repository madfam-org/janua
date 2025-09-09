# Plinto — BIZ\_DEV.md

**Company:** Plinto (plinto.dev) by **Aureo Labs** (aureolabs.dev), a **MADFAM** company (madfam.io)
**Doc status:** Draft v1.0 (Monetization & Internal Adoption)
**Owners:** BizOps, Product, Finance, Legal, Platform Eng
**Scope:** Pricing & packaging, payments architecture (Conekta MX + Fungies.io MoR INTL), GTM, revenue ops, and internal rollout across MADFAM products.

---

## 0) Executive Summary

Plinto is the **secure substrate for identity**. Our business strategy is **product‑led with an enterprise overlay**. We will monetize via tiered subscriptions with usage‑based overages, sell enterprise add‑ons (SSO/SCIM, residency, audit), and leverage **Conekta** for **Mexico‑based customers** (MXN) and **Fungies.io** as **Merchant of Record** (MoR) for international customers (multi‑currency, tax handling).

**Why this wins:** developer‑fast integration, edge‑level performance, and a strong **“own your identity”** story—in both LATAM and global markets.

---

## 1) ICPs & Segments

**Primary ICPs**

1. **B2B SaaS** teams (Seed–Series B) needing auth/RBAC/SSO quickly.
2. **Mid‑market/Enterprise** platforms seeking **region pinning** and **policy control** without lock‑in.
3. **Internal platforms** at MADFAM/Aureo Labs to unify login, entitlements, and billing.

**Secondary ICPs**

* Agencies/consultancies building multi‑tenant apps.
* Data/AI products needing edge verification and auditability.

**Geography**

* **Mexico**: price‑localized MXN via Conekta.
* **International**: USD/EUR via Fungies.io (MoR).

---

## 2) Packaging & Pricing (Alpha→GA)

> Pricing is **indicative**; finalize after 3 design‑partner pilots and willingness‑to‑pay interviews.

### 2.1 Unit(s) of value

* **Monthly Active Users (MAU)** per tenant (default).
* **Add‑ons** by capability: SSO/SCIM, residency, advanced audit, premium support.
* **Overages** for MAU beyond plan caps.

### 2.2 Tiers (public)

* **Community (Free)** — up to **2,000 MAU**; 1 region; core auth + passkeys; basic audit; fair‑use rate limits; community support.
* **Pro** — from **\$69 USD / \$1,200 MXN** / month; up to **10,000 MAU**; 2 regions; orgs/teams/RBAC; webhooks; custom roles; email support; overage **\$10 USD / \$180 MXN per 1,000 MAU**.
* **Scale** — from **\$299 USD / \$5,200 MXN** / month; up to **50,000 MAU**; 3 regions; higher limits; priority email; overage **\$8 USD / \$140 MXN per 1,000 MAU**.
* **Enterprise** — custom; includes SSO (SAML/OIDC), SCIM, residency controls, advanced audit, DPA/SLA, support SLAs, security review.

> **Optional add‑ons** (Pro/Scale/Enterprise):
>
> * **SSO/SCIM** (+\$199 USD / \$3,500 MXN / month)
> * **Advanced Audit** (+\$79 USD / \$1,400 MXN / month)
> * **Region Pinning** (+\$49 USD / \$850 MXN / month per region)
> * **Premium Support** (+\$149 USD / \$2,600 MXN / month)

### 2.3 Price localization policy

* Mexico‑based entities (billing address in MX): show MXN; others show USD (or local currency via MoR).
* Exchange rate review monthly; do **not** reprice existing subscribers—only new contracts.

### 2.4 Discounts & terms

* Startups (<\$1M ARR): 20% year‑1 on Pro/Scale (requires verification).
* Annual prepay: 15% discount; **no refunds** after 30 days; service credits only.
* Non‑profits/education: case‑by‑case up to 30%.

### 2.5 Overage & throttling

* Overage billed monthly in arrears based on **highest daily MAU** in period.
* Soft‑throttle after 20% over cap; notify via email/webhooks; emergency uplift toggle for 7 days.

---

## 3) Payments & Billing Architecture

**Single domain:** `plinto.dev`
**Checkout Rule:** detect customer region and legal entity to route payments stack.

### 3.1 Routing logic

* **If Billing Country = Mexico** → **Conekta** (MXN).
* **Else (International)** → **Fungies.io** (MoR; currency shown by locale, collected/settled by Fungies).

### 3.2 Conekta (Mexico)

* **Use cases**: card payments, bank transfers, and common local payment methods.
* **What we implement**: hosted checkout/PCI‑scope‑reduced capture, webhooks for payment success/failure, dunning/retries, refunds, dispute workflows.
* **Tax**: display prices in **MXN**; VAT handling per Mexican regulations (consult Legal/Tax).
* **Invoices**: provide tax‑compliant invoices/receipts; if CFDI/e‑invoicing is required by a customer, engage our local e‑invoicing provider (outside this doc’s scope).

### 3.3 Fungies.io (International, MoR)

* **Role**: acts as **Merchant of Record**, handling card acceptance, **tax/VAT/GST** calculation and remittance in supported regions, currency conversion, and compliance (incl. PSD2/SCA flows where applicable).
* **What we implement**: checkout links/widgets, customer portal, subscription management, webhooks to sync entitlements, refunds/chargebacks via MoR process.

### 3.4 Subscription model & entitlements

* **Source of truth**: Plinto **Billing Service** maintains **Subscriptions**, **Plans**, **Entitlements**.
* **External providers** (Conekta/Fungies) emit events → we reconcile to **active\_until**, **plan\_id**, **add\_ons\[]**.
* **App gating**: each product calls Plinto’s **Entitlements API** to determine access/features.

### 3.5 Dunning & recovery

* Retries: exponential backoff schedule (3/7/14 days).
* Downgrade to **grace mode** for 7 days; then limit admin actions; after 21 days, suspend non‑critical features.
* Email/SMS (opt‑in) notifications; in‑product banners via Admin.

### 3.6 Refunds & disputes

* Self‑serve refunds within **7 days** (Pro/Scale) when low/no usage.
* Chargebacks handled via provider; we add **customer notes** and adjust entitlements promptly.

### 3.7 Revenue recognition & reporting

* Finance receives monthly export: subscriptions, MRR movements (new/expansion/contraction/churn), taxes, fees; separate MX (Conekta) and INTL (Fungies) ledgers.
* Use **event‑based** bookings; recognize revenue ratably over service period.

---

## 4) Internal Adoption (MADFAM‑wide)

### 4.1 Integration sequence (90 days)

1. **Forge Sight** — replace Clerk; dogfood all core features.
2. **Internal tools** — MADFAM intranet, dashboards; validate org/RBAC.
3. **Aureo Labs apps** — any B2B or dev‑facing properties; enable SSO pilots.
4. **Customer apps** — prioritize those needing audit/regional controls.

### 4.2 Standards & invariants

* **AuthAdapter** as the integration seam; reversible switch.
* **Single MADFAM Account** backed by Plinto; cross‑product SSO.
* **Entitlements API** centralizes **plans/add‑ons**; each product reads features from Plinto.
* **Telemetry**: instrument signup→activation, MAU, and conversion per product.

### 4.3 Internal chargeback (transfer pricing)

* Each product is charged internal **transfer price** (at cost + 10%) per MAU over community tier to incentivize efficient usage; Finance settles quarterly.
* Enterprise add‑ons used internally (e.g., SSO) are tracked but **zero‑rated**.

### 4.4 Data & privacy

* Tenants per product; orgs per customer; least privilege on cross‑product data access.
* Audit trail shared services; access via Admin with role constraints.

---

## 5) GTM: Motions, Channels, Offers

### 5.1 Motions

* **PLG (self‑serve)** — free tier + 90‑minute integration path, cookbook recipes, sample apps.
* **Enterprise overlay** — security review kit (SOCs roadmap, DPA), pilots, success plans, executive sponsor.

### 5.2 Channels

* **Dev content**: blog, examples, “Why we built Plinto” case study (Forge Sight).
* **Communities**: HN, Reddit r/webdev/r/devops, Product Hunt.
* **Partners**: Vercel ecosystem, Cloudflare community, Railway users.
* **LATAM focus**: Spanish docs, local talks/webinars, founder rounds with Mexico dev communities.

### 5.3 Launch offers

* **Founding Teams**: first 100 signups get Scale for 6 months at Pro price.
* **Startup program**: credits + advisory for incubators/accelerators.

---

## 6) SLAs, Support, and Success

* **Community**: community forum + 72h best‑effort.
* **Pro/Scale**: weekday email, 24h response; incident comms via status page.
* **Enterprise**: support SLOs, named TAM, incident bridge; credits for SLO misses.
* **Availability target**: 99.95%; RPO ≤ 5m; RTO ≤ 30m.

---

## 7) KPIs & Dashboards

* **Revenue**: MRR, NRR, GRR, ARPA, expansion \$, logo churn %, gross margin.
* **Funnel**: visits → signups → first token → first protected route → MAU → converted.
* **Product**: passkey adoption %, verify p95 latency, auth success rate, token reuse incidents.
* **Ops**: deliverability (bounce/complaint), WAF/ratelimit hits, incident count/MTTR.
* **Billing**: dunning rate, days‑to‑recovery, refund %, chargeback rate.

**Targets (alpha→GA)**

* Signup→first protected route ≥ **60%** within 24h.
* Verify p95 **< 50ms** (edge hot).
* Dunning recovery **> 55%** within 14 days.
* NRR **> 115%** at month 12.

---

## 8) Pricing Calculator (internal)

**MAU‑based** monthly price formula (non‑enterprise):

```
base_price(tier) + add_ons + overage_price_per_1k * ceil(max(0, (MAU - tier_cap)/1000))
```

**Example**: Pro tier, 14k MAU, +SSO add‑on
`$69 + $199 + $10 * ceil((14k - 10k)/1k) = $69 + $199 + $40 = $308 / mo`

**MXN mirror** uses the MX price list (not FX‑linked for existing contracts).

---

## 9) Legal & Compliance Notes (business)

* **Terms & Privacy**: two versions—MX (Conekta) and INTL (MoR).
* **Data Protection**: DPA + SCCs for international customers; LFPDPPP (MX) alignment.
* **Tax**: MoR handles INTL indirect taxes; MX handled via our stack; Finance to reconcile monthly.
* **Sanctions/KYC**: rely on provider screening where available; high‑risk flags escalate to manual review.

---

## 10) Risks & Mitigations (Revenue)

* **Payments fragmentation** → clear routing logic + redundant checkout options.
* **Deliverability drop** → IP warming, double‑opt‑in, Turnstile on risky flows.
* **Feature creep** → packaging guardrails; enterprise add‑ons quarantined from Community.
* **Margin squeeze** (provider fees) → price floors + annual review; negotiate MoR rates at volume.

---

## 11) Timeline (next 90 days)

* **Week 0–2**: finalize price cards, checkout flows, provider webhooks; seed 3 design partners (MX + INTL).
* **Week 3–6**: in‑product upgrade, dunning flows, Admin entitlements; publish docs + calculator.
* **Week 7–10**: launch Pro/Scale public; start Enterprise pilots; publish case study.
* **Week 11–12**: review KPIs; adjust caps/overage; prep GA materials.

---

## 12) Appendices

### A) SKU Matrix

| SKU             | Includes                            | Notes                          |
| --------------- | ----------------------------------- | ------------------------------ |
| PLINTO-COMM     | Core features, 1 region, 2k MAU cap | Free; community support        |
| PLINTO-PRO      | +Orgs/RBAC, 2 regions, 10k cap      | Overage billed                 |
| PLINTO-SCALE    | Higher caps/limits, 3 regions       | Overage billed                 |
| ADDON-SSO       | SAML/OIDC, SCIM                     | Enterprise or Pro/Scale add‑on |
| ADDON-AUDIT     | Advanced audit, retention           |                                |
| ADDON-RESIDENCY | Region pinning per region           |                                |
| ADDON-SUPPORT   | Premium support                     |                                |

### B) Trial & Refund Policy (public summary)

* 14‑day trial on Pro; full features except SSO/SCIM.
* 7‑day refund window with usage criteria.

### C) Event Mapping (billing sync)

* `subscription.created|updated|canceled` → update entitlements.
* `invoice.paid|payment_failed` → set `active_until`.
* `chargeback.created|resolved` → suspend/reinstate.

### D) Sales Cheatsheet (EN/ES)

* **EN**: *Edge‑fast, ownable identity. Replace vendor lock‑in with a secure substrate you control.*
* **ES**: *Identidad veloz en el borde y bajo tu control. Un sustrato seguro y unificador para tus productos.*

---
name: fintech-onboarding-excellence
description: >-
  World-Class FinTech & InsurTech Onboarding Design System and Architecture Standard.
  Applies modern UI tokens, 30-minute continuous flows, DigiLocker 1-click pulls,
  Account Aggregator rails, 8-tier Indian name resolution, deterministic rules,
  visual fraud ring graphs, and grounded AI assistant copilot interactions.
---

# FinTech & InsurTech Onboarding Excellence Standard

This skill establishes the engineering, architectural, and UI/UX benchmark for mission-critical Indian FinTech and InsurTech onboarding platforms, specifically compliant with IRDAI POSP Guidelines, DPDP Act 2023, and NPCI/UIDAI regulatory standards.

---

## 1. Core Industry Baselines & Excellence Targets (8.0+ Mandate)

Every capability must surpass the traditional industry baseline and achieve $\ge 9.0/10$ across all eight dimensions:

| Dimension | Legacy Industry Baseline | PolicyNest Excellence Target | Key Implementation Mechanisms |
| :--- | :---: | :---: | :--- |
| **1. Candidate Experience** | 3.5 / 10 | **9.5+ / 10** | 30-Minute Continuous Session, 1-Click DigiLocker Import, Live Pre-Capture Quality Gate, Vernacular Voice Guidance. |
| **2. Integration Strategy** | 4.0 / 10 | **9.5+ / 10** | DigiLocker e-KYC XML, Account Aggregator FIP, NPCI IMPS Penny Drop, India Post PIN, RBI IFSC. |
| **3. Bottleneck Eradication** | 4.2 / 10 | **9.8+ / 10** | 60%+ Straight-Through Processing (STP), <45s auto-pass, 0-hour queue wait, end-to-end LMS certification. |
| **4. Fraud Defense** | 4.5 / 10 | **9.6+ / 10** | Deterministic SHA-256 deduplication, mule bank account checks, visual fraud ring network graphs, quarantine queues. |
| **5. Reviewer Productivity** | 4.8 / 10 | **9.7+ / 10** | Focused micro-review cards, split-screen document preview, keyboard triage hotkeys (`A`/`R`/`E`), SLA timers. |
| **6. Decision Intelligence** | 5.2 / 10 | **9.8+ / 10** | 8-Tier Indian Name Matching (token, phonetic, initial, matrimonial), Non-Auto-Reject Guardrail, Grounded AI Copilot. |
| **7. System Resilience** | 6.0 / 10 | **9.5+ / 10** | SSE real-time telemetry with auto-reconnect, optimistic client state, connector fallback architecture. |
| **8. Statutory Rigor** | 8.1 / 10 | **9.9+ / 10** | 0.0% regulatory leakage on 600-case ground-truth test set, DPDP 12-digit Aadhaar masking, verifiable QR certificates. |

---

## 2. Design System & UI/UX Standards

### 2.1 Palette & Typography
- **Primary / Brand**: Deep Indigo & Cobalt (`#1e293b`, `#2547ea`, `#1d36d7`).
- **Success / Verified**: Emerald Green (`#059669`, `#10b981`, `#ecfdf5`).
- **Warning / Rework**: Warm Amber (`#d97706`, `#f59e0b`, `#fffbeb`).
- **Danger / Fraud Alert**: Rose & Crimson (`#dc2626`, `#ef4444`, `#fef2f2`).
- **Neutral Canvas**: Slate & Pearl (`#f8fafc`, `#ffffff`, border `#e2e8f0`).
- **Typography**: Inter / Geist sans-serif with strict optical sizing, numerical tabular figures for financial data and timers.

### 2.2 Micro-Interactions & Glassmorphism
- Ambient translucent cards (`backdrop-blur-md bg-white/90 border border-slate-200/80 shadow-sm`).
- Instant upload acknowledgment (<200ms) with smooth 850ms step transitions.
- Live canvas pre-capture guidance with corner alignment guides and real-time blur/glare indicators.
- Pulsing audio waveform indicators for multilingual voice copilot assistance.

---

## 3. Autonomous Fraud Ring & Identity Syndicate Defense

### 3.1 Detection Rules
1. **Document Deduplication (`ANOMALY_DUPLICATE_DOCUMENT`)**:
   Matches `sha256_hash` of any uploaded document against historical uploads across disparate applicant accounts.
2. **Mule Account Diversion (`ANOMALY_SHARED_BANK_ACCOUNT`)**:
   Detects identical IFSC and account numbers registered under disparate PANs.
3. **Contact Stacking (`ANOMALY_IDENTITY_STACKING`)**:
   Detects single phone/email linked to $\ge 3$ distinct PAN profiles.

### 3.2 Visual Quarantine
Applications triggering fraud anomalies are quarantined immediately:
- Automated approval is blocked (`auto_pass_eligible = False`).
- File is escalated to Senior Compliance & Fraud Desk with visual collision graphs.

---

## 4. Grounded AI Assistant (InsurTech Copilot)

An always-available, floating copilot widget grounded in:
1. Active application data (extracted OCR fields, confidence scores, validation outcomes).
2. Official IRDAI POSP Guidelines (Age $\ge 18$, Class 10 pass, Individual PAN 'P', single-broker exclusivity).
3. Plain-language explanations of rework instructions in English and Hindi.

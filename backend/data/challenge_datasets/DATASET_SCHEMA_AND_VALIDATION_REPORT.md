# PolicyNest Dataset Schema & Comprehensive Validation Report

> **Technical Specification & Audit of Source Datasets**  
> **Project:** PolicyNest AI-First POSP Onboarding Platform  
> **Source:** Masters' Union Applied AI Challenge Data Pack (`PS-01_posp_applications.xlsx` and `PS-01_document_review_test_set.xlsx`)

---

## 1. Executive Summary & Dataset Inventory

The PolicyNest data repository consists of two official Excel workbooks containing 8 primary operational and benchmarking datasets. These datasets provide the empirical foundation for training, calibrating, and benchmarking the AI-first onboarding system.

| Dataset File | Format | Record Count | Column Count | Primary Role | Source Workbook |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `applications.csv` | CSV / Relational | 3,018 rows | 27 columns | Historical 9-month operational log (Jan–Sep 2026) | `PS-01_posp_applications.xlsx` (Sheet 1) |
| `stage_events.csv` | CSV / Event Log | 21,188 rows | 5 columns | Complete event sourcing audit trail of all lifecycle events | `PS-01_posp_applications.xlsx` (Sheet 2) |
| `ops_team.csv` | CSV / Master | 22 rows | 7 columns | Operations reviewer roster, shifts, tenure, and cost metrics | `PS-01_posp_applications.xlsx` (Sheet 3) |
| `monthly_funnel.csv` | CSV / Aggregated | 9 rows | 8 columns | Monthly operational KPIs, volumes, touches, and TAT | `PS-01_posp_applications.xlsx` (Sheet 4) |
| `documents.csv` | CSV / Test Set | 3,600 rows | 13 columns | Labelled document evaluation test set (600 apps x 6 docs) | `PS-01_document_review_test_set.xlsx` (Sheet 1) |
| `application_truth.csv` | CSV / Benchmark | 600 rows | 12 columns | Ground truth application-level decisions and root causes | `PS-01_document_review_test_set.xlsx` (Sheet 2) |
| `reason_codes.csv` | CSV / Taxonomy | 14 rows | 3 columns | Official IRDAI/PolicyNest defect taxonomy and verdicts | `PS-01_document_review_test_set.xlsx` (Sheet 3) |
| `PS-01_posp_applications.xlsx` | Excel (.xlsx) | 4 sheets | - | Master source workbook for historical operations | Original Challenge Pack |
| `PS-01_document_review_test_set.xlsx` | Excel (.xlsx) | 3 sheets | - | Master source workbook for document review benchmark | Original Challenge Pack |

---

## 2. Table-by-Table Detailed Schema Specifications

### 2.1 `applications.csv` (Historical Cohort — 3,018 records)
Represents all POSP applications initiated between January 1, 2026 and September 30, 2026 across 4 acquisition channels (Organic, Agent Referral, Digital Campaign, Campus/Partner).

| Column Name | Data Type | Nullable | Description / Business Meaning | Sample Values |
| :--- | :--- | :--- | :--- | :--- |
| `application_id` | String (PK) | No | Unique identifier for each onboarding application | `APP-00001`, `APP-03018` |
| `created_at` | Timestamp | No | Application initiation timestamp | `2026-01-02 09:14:22` |
| `channel` | Categorical | No | Sourcing channel (`Organic`, `Agent Referral`, `Digital Campaign`, `Campus`) | `Organic`, `Digital Campaign` |
| `state` | String | No | Applicant declared state of residence (28 states / UTs) | `Uttar Pradesh`, `Maharashtra` |
| `city` | String | No | Applicant declared city | `Agra`, `Pune`, `Kanpur` |
| `applicant_name` | String | No | Full name declared on web application form | `Sachin Chand Mittal` |
| `gender` | Categorical | No | Self-declared gender (`MALE`, `FEMALE`, `OTHER`) | `MALE`, `FEMALE` |
| `dob_declared` | Date | No | Declared date of birth (`YYYY-MM-DD`) | `2000-05-14` |
| `mobile_masked` | String | No | Masked contact phone number | `XXXXXX4920` |
| `pan_declared` | String | No | 10-character PAN string declared by user | `ABCDE1234F` |
| `aadhaar_masked` | String | No | Last 4 digits of Aadhaar | `XXXX-XXXX-9744` |
| `education_declared`| Categorical | No | Declared education (`Class 10`, `Class 12`, `Graduate`, `Post-graduate`) | `Class 12`, `Graduate` |
| `bank_name` | String | No | Bank name declared for commission payouts | `State Bank of India`, `HDFC Bank` |
| `ifsc` | String | No | Bank branch IFSC code (11 chars) | `SBIN0001234` |
| `account_last4` | String | No | Last 4 digits of bank account number | `7526` |
| `docs_submitted_at`| Timestamp | Yes | Timestamp when all 5 initial documents were submitted | `2026-01-02 10:30:00` |
| `kyc_verified_at` | Timestamp | Yes | Timestamp when human reviewer verified KYC | `2026-01-03 14:15:00` |
| `training_started_at`| Timestamp| Yes | Timestamp when applicant started 15-hour LMS training | `2026-01-04 09:00:00` |
| `training_completed_at`| Timestamp| Yes | Timestamp when 15 hours of training were completed | `2026-01-06 17:30:00` |
| `exam_passed_at` | Timestamp | Yes | Timestamp when applicant passed POSP exam | `2026-01-07 11:45:00` |
| `certified_at` | Timestamp | Yes | Final issuance of IRDAI POSP certification | `2026-01-07 12:00:00` |
| `status` | Categorical | No | Final application status (`CERTIFIED`, `REJECTED`, `DROPPED_OUT`, `IN_PROGRESS`) | `CERTIFIED`, `DROPPED_OUT` |
| `rejection_reason`| String | Yes | Primary reason code if rejected or dropped | `DOB_MISMATCH`, `EDU_NOT_ELIGIBLE` |
| `ops_reviewer_id` | String (FK) | Yes | Identifier of Ops reviewer assigned (`REV-01` to `REV-22`) | `REV-04` |
| `manual_touches` | Integer | No | Count of manual review interactions performed | `1`, `3`, `5` |
| `resubmissions` | Integer | No | Count of document rework cycles required | `0`, `1`, `2` |
| `hours_to_certify`| Float | Yes | Total elapsed time from creation to certification in hours | `118.4`, `74.2` |

---

### 2.2 `stage_events.csv` (Event Sourcing Audit Trail — 21,188 records)
Granular chronological event logs tracking every state transition, reviewer action, document re-upload, training module progress, and exam attempt.

| Column Name | Data Type | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :--- | :--- |
| `application_id` | String (FK) | No | Reference to `applications.csv` | `APP-00001` |
| `event_time` | Timestamp | No | Exact ISO timestamp of the event | `2026-01-02 10:30:15` |
| `actor` | Categorical | No | Actor initiating event (`APPLICANT`, `OPS_REVIEWER`, `SYSTEM`, `TRAINING_ENGINE`) | `APPLICANT`, `OPS_REVIEWER` |
| `event` | Categorical | No | Event type (`APPLICATION_STARTED`, `DOCS_UPLOADED`, `KYC_REJECTED`, `REWORK_REQUESTED`, `TRAINING_COMPLETED`, `EXAM_PASSED`, `CERTIFICATE_ISSUED`) | `DOCS_UPLOADED`, `KYC_APPROVED` |
| `note` | String | Yes | Free-text reviewer comment or system diagnostic payload | `Re-upload requested for Class 10 marksheet: blurry image` |

---

### 2.3 `documents.csv` (Evaluation Benchmark Test Set — 3,600 records)
Evaluation test set comprising exactly 600 applications with 6 documents each (PAN, Aadhaar Front, Aadhaar Back, Class 10 Marksheet, Bank Cheque, Selfie).

| Column Name | Data Type | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :--- | :--- |
| `doc_id` | String (PK) | No | Unique document identifier | `DOC-00001`, `DOC-03600` |
| `application_id` | String (FK) | No | Reference to `application_truth.csv` | `APP-26001` |
| `doc_type` | Categorical | No | Document category (`PAN`, `AADHAAR_FRONT`, `AADHAAR_BACK`, `CLASS10_MARKSHEET`, `BANK_DOCUMENT`, `SELFIE`) | `PAN`, `SELFIE` |
| `image_quality` | Categorical | No | Image quality flag (`OK`, `BLURRY`, `CROPPED`, `GLARE`) | `OK`, `BLURRY` |
| `ocr_confidence` | Float | Yes | OCR engine character recognition confidence score (0.0 to 1.0) | `0.946`, `0.712` |
| `ocr_text` | Text | Yes | Raw text extracted by OCR engine from the document | `INCOME TAX DEPARTMENT ...` |
| `name_extracted` | String | Yes | Name parsed from OCR text | `SACHIN CHAND MITTAL` |
| `dob_extracted` | Date/String | Yes | Date of birth parsed from OCR text | `01/02/2008` |
| `id_number_extracted`| String | Yes | Extracted ID number (PAN, Aadhaar last 4, roll number, account/IFSC) | `NREPM4880W` |
| `face_match_score` | Float | Yes | Biometric similarity score against PAN photo (0.0 to 1.0; only on SELFIE) | `0.91`, `0.58` |
| `human_verdict` | Categorical | No | Human reviewer verdict (`PASS`, `REUPLOAD`, `REJECT`) | `PASS`, `REUPLOAD` |
| `human_reason_code`| Categorical | Yes | Defect reason code from official taxonomy | `IMAGE_BLURRY`, `NAME_MISMATCH` |
| `reviewer_minutes` | Float | No | Time in minutes spent by human reviewer evaluating this document | `3.2`, `8.5` |

---

### 2.4 `application_truth.csv` (Ground Truth Benchmark Decisions — 600 records)
Definitive benchmark ground truth for evaluating policy engines. Provides declared form values, external verification results, expected decision, and root-cause reason codes.

| Column Name | Data Type | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :--- | :--- |
| `application_id` | String (PK) | No | Unique application ID (APP-26000 to APP-26599) | `APP-26001` |
| `declared_name` | String | No | Name entered by applicant during registration | `Sachin Chand Mittal` |
| `declared_dob` | Date | No | Date of birth entered by applicant | `01/02/2008` |
| `declared_pan` | String | No | 10-digit PAN entered by applicant | `NREPM4880W` |
| `declared_education`| Categorical | No | Declared educational qualification | `Class 12`, `Graduate` |
| `declared_state` | String | No | Declared residential state | `Uttar Pradesh` |
| `penny_drop_name_returned`| String| Yes | Account holder name returned by bank penny-drop API | `S C MITTAL` |
| `irdai_posp_registry_hit`| Boolean | No | Whether PAN was found registered with another insurer (`True`/`False` or `Yes`/`No`) | `No`, `Yes` |
| `final_decision` | Categorical | No | Benchmark ground truth decision (`APPROVE`, `NEEDS_MORE_INFO`, `REJECT`) | `APPROVE`, `REJECT` |
| `decision_reasons`| String | Yes | Semicolon-delimited reason codes | `EDU_NOT_ELIGIBLE; POOR_QUALITY` |
| `name_match_category`| Categorical| No | Name pattern classification (`exact`, `initial`, `swap`, `middle added`, `spelling`, `different`) | `exact`, `swap` |
| `is_hard_case` | Boolean | No | Flag indicating edge cases requiring deep inspection | `0` or `1` |

---

### 2.5 `ops_team.csv` (Operations Team Roster — 22 records)
Captures the 22-member manual onboarding operations team, including tenure, shifts, processing speed, and fully-loaded hourly cost.

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `reviewer_id` | String (PK) | Reviewer identifier (`REV-01` to `REV-22`) |
| `team` | Categorical | Operational sub-team (`Tier 1 Ops`, `Tier 2 Senior Ops`, `Fraud Desk`) |
| `tenure_months` | Integer | Months of experience in POSP onboarding operations (2 to 36 months) |
| `shift` | Categorical | Work shift (`Morning`, `Evening`, `General`) |
| `speed_index` | Float | Productivity multiplier relative to baseline reviewer (0.80 to 1.35) |
| `loaded_cost_inr_per_hour` | Float | Total cost to company per hour in INR (₹280 to ₹520/hr) |
| `applications_handled_jan_sep`| Integer | Cumulative historical cases reviewed |

---

### 2.6 `monthly_funnel.csv` (Historical Funnel Metrics — 9 records)
Aggregates monthly volume, certification yield, dropout rates, touches, and turnaround time from January to September 2026.

| Month | Applications | Certified | Dropped | Rejected | Median TAT (Hrs) | Avg Touches | Certification Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Jan 2026 | 280 | 148 | 98 | 34 | 124.5 | 3.4 | 52.8% |
| Feb 2026 | 295 | 160 | 99 | 36 | 120.0 | 3.3 | 54.2% |
| Mar 2026 | 320 | 175 | 108 | 37 | 118.2 | 3.2 | 54.7% |
| Apr 2026 | 340 | 182 | 118 | 40 | 116.0 | 3.1 | 53.5% |
| May 2026 | 355 | 195 | 120 | 40 | 115.4 | 3.1 | 54.9% |
| Jun 2026 | 360 | 201 | 119 | 40 | 114.8 | 3.0 | 55.8% |
| Jul 2026 | 350 | 192 | 118 | 40 | 115.0 | 3.1 | 54.8% |
| Aug 2026 | 358 | 198 | 120 | 40 | 114.2 | 3.0 | 55.3% |
| Sep 2026 | 360 | 203 | 117 | 40 | 113.6 | 3.0 | 56.4% |

---

### 2.7 `reason_codes.csv` (Defect Taxonomy — 14 records)
The complete standard taxonomy of rejection, rework, and review reason codes.

| Reason Code | Verdict Type | Operational Meaning | Action Required |
| :--- | :--- | :--- | :--- |
| `IMAGE_BLURRY` | REUPLOAD | Text not legible at normal zoom | Request daylight photograph with sharp focus |
| `IMAGE_CROPPED` | REUPLOAD | Part of the document is outside frame | Request full document with all 4 corners visible |
| `IMAGE_GLARE` | REUPLOAD | Light reflection hides a required field | Request photograph without direct flash or glare |
| `PAN_FORMAT_INVALID` | REJECT | PAN does not match regex `AAAAA9999A` | Hard rejection. Permanent disqualification of document |
| `PAN_NOT_INDIVIDUAL` | REJECT | 4th char is not 'P' (Company/Trust) | Hard rejection. Individual status required |
| `EDU_NOT_ELIGIBLE` | REJECT | Class 10 not passed or board invalid | Hard rejection. Minimum secondary education not met |
| `NAME_MISMATCH` | REJECT | Document belongs to different person | Hard rejection. Flagged to Senior Reviewer/Fraud Desk |
| `NAME_SPELLING_VARIANT`| NEEDS_INFO| Same person, slight phonetic/spelling variation | Request secondary proof, affidavit, or confirmation |
| `DOB_MISMATCH` | NEEDS_INFO| DOB differs between documents | Request clarification; PAN treated as reference anchor |
| `BANK_NAME_MISMATCH` | NEEDS_INFO| Penny-drop name does not match applicant | Request cheque in applicant's own individual name |
| `FACE_MATCH_LOW` | NEEDS_INFO| Selfie vs PAN photo score < 0.60 | Request new clear selfie in neutral background |
| `UNDERAGE` | REJECT | Under 18 years on application date | Hard rejection. May reapply upon turning 18 |
| `ALREADY_REGISTERED`| REJECT | Active POSP with another insurer/broker | Hard rejection. Requires NOC from existing sponsor |
| `REVIEWER_DISCRETION`| NEEDS_INFO| Edge cases requiring subjective review | Human reviewer custom note delivered to applicant |

---

## 3. Data Integrity & Validation Findings

During automated inspection of the original datasets, the following validation characteristics were confirmed:
1. **Referential Integrity:** All 21,188 events in `stage_events.csv` reference valid `application_id` entries in `applications.csv`. All 3,600 documents in `documents.csv` map to the 600 applications in `application_truth.csv`.
2. **Aadhaar Masking Compliance:** All records in both `applications.csv` and `documents.csv` store only the last 4 digits of Aadhaar (prefixed with `XXXX-XXXX-`). Zero 12-digit plaintext Aadhaar numbers exist.
3. **Event Timeline Consistency:** All timestamps in `stage_events.csv` follow strict monotonic ordering (`APPLICATION_STARTED` <= `DOCS_UPLOADED` <= `KYC_VERIFIED` <= `TRAINING_COMPLETED` <= `EXAM_PASSED` <= `CERTIFICATE_ISSUED`).
4. **Benchmark Distribution:** The 600 ground truth test cases in `application_truth.csv` are distributed across: 272 APPROVE (45.3%), 184 NEEDS_MORE_INFO (30.7%), and 144 REJECT (24.0%), providing balanced evaluation power across all defect types.
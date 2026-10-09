# Field unification proposal

Status: **sections A and B applied (alias map in `backend/templates/scrutiny_reports/field_aliases.json`); section C left unchanged and listed as questions for the lawyer in `TEMPLATE_PREP_NOTES.md`.** The text below is the original proposal. All 10 source reports are converted (9 templates, 216 distinct fields, 17 loops). Rule used: merge only when the bank form asks the same question in substance; keep separate where bank wording changes the meaning. Applying a merge means renaming the field in the template (`{{ old }}` to `{{ canonical }}`), the manifest, and adding an alias entry so older data and drafts still resolve.

## A. Proposed merges (same question)

| Canonical name | Replaces | Templates affected | Confidence |
|---|---|---|---|
| `property_tax_payment_status` | `property_tax_paid_status` (IDFC), `part3_taxes_paid` (TATA) | IDFC, TATA | High |
| `minor_claims` | `part3_minor_interest` (TATA) | TATA | High |
| `sarfaesi_conclusion` | `part3_sarfaesi_enforceable` (TATA) | TATA | High |
| `mortgage_approval_status` | `part3_other_permissions` (TATA) | TATA | High |
| `na_conversion_status` | `part3_conversion_permission` (TATA) | TATA | High |
| `stamp_duty_status` | `part3_stamp_duty` (TATA, SHIN) | TATA, SHIN | High |
| `mutation_extract_status` | `part3_revenue_mutation` (TATA) | TATA | Medium (Tata also has a separate municipal mutation question, kept as `municipal_mutation_status`) |
| `search_date` | `search_challan_date` (IDFC, KOTAK) | IDFC, KOTAK | Medium (the source line reads "Challan no. X and Receipt no. Y dated D", which is the date of the search) |
| `mortgage_creatable` | `mortgage_requirement` (CHOLA) | CHOLA | Medium (Chola's wording is a sentence about whether an equitable mortgage is required; the others answer "is a mortgage possible") |

Shinhan special case: Shinhan has two tax questions in one report (row 6 land revenue / building tax, row 22(a) property tax), so it cannot use one name for both. Row 6 already uses `property_tax_payment_status`; row 22(a) keeps `property_tax_paid_status`, which therefore survives for Shinhan only.

## B. Renames only (no merge, drop the `part3_` prefix)

These exist in one template only and the `part3_` prefix refers to that form's section number, not to the question.

| Current | Proposed |
|---|---|
| `part3_litigation` | `litigation_status` |
| `part3_land_use` | `land_use_status` |
| `part3_municipal_limits` | `municipal_limits_status` |
| `part3_leasehold_details` | `leasehold_terms_details` |
| `part3_municipal_mutation` | `municipal_mutation_status` |
| `part3_govt_grant` | `govt_grant_status` |
| `part3_local_laws` | `local_laws_effect` |
| `part3_sanctions_reviewed` | `sanctions_reviewed_status` |

## C. Needs your call (could be the same question, wording differs)

| Fields | Why it is unclear |
|---|---|
| `title_marketable_status` (SHIN q2), `title_clear_marketable_status` (HDFC q7), `title_status` (TATA) | All ask whether title is clear and marketable, but HDFC q7 also covers encumbrances and minor / HUF claims, and Shinhan q2 also covers ability to create a valid mortgage. |
| `present_owner_names` (SHIN), `transferor_names` (TATA), `record_owner_name` (IDFC, INDUS), `land_owner_names` (IDFC) | All are "who owns the property now / the seller", but they come from different sources (revenue record, search, agreement). |
| `local_central_laws_effect` (INDUS, SHIN), `part3_local_laws` (TATA) | Tata lists agricultural, weaker-section and minority laws; the others list Land Acquisition and Urban Ceiling Acts. |
| `lease_tenure_details` (ICICI, JIO, SHIN), `part3_leasehold_details` (TATA) | ICICI / Jio ask for the tenure; Tata and Shinhan ask for lease terms, lessor and NOC. |
| `declaration_title_statement` (IDFC), `certificate_title_statement` (ICICI, JIO, INDUS, SHIN) | Same job (the certificate paragraph) under a different heading. |
| `advocate_final_opinion` (IDFC), `opinion_conclusion` (the rest) | IDFC's is a standalone final paragraph; the others are the tail of the ownership sentence. |
| `documents_13_years_scrutinized` (ICICI, JIO), `title_history_traced_status` (HDFC) | Both about covering 13 years, but one is the lawyer's scrutiny of originals and the other is tracing the history. |

## D. Deliberately not merged

- Bank reference numbers: `reference_number`, `application_number`, `los_id`, `webtop_number` are different identifiers; a report can print two of them.
- `loan_product` (TATA) vs `loan_type` and `loan_purpose` (ICICI, JIO): different questions.
- `search_conclusion` vs `search_flow_conclusion`: the second states only that the flow of title is reflected in the search.
- `property_tenure` (choice) vs the eight `tenure_*` rows (HDFC): one asks which kind, the others answer a table row each.
- `boundary_*` (scalar, per property) vs `land_parcels` (loop, per gat): different structure.
- Document loops share names (`documents_verified`, `documents_pre_disbursement`, `documents_post_disbursement`) but the item fields differ (`nature, date, form` in IDFC; `date, description, form` in SHIN; `description` alone elsewhere). Suggested follow-up: make `description` the one required item field and `date` / `form` optional; this renames IDFC's `nature` to `description`.

## E. Effect if A and B are approved

- In A, 8 names disappear (`part3_taxes_paid`, `part3_minor_interest`, `part3_sarfaesi_enforceable`, `part3_other_permissions`, `part3_conversion_permission`, `part3_revenue_mutation`, `search_challan_date`, `mortgage_requirement`), `part3_stamp_duty` becomes `stamp_duty_status`, and `property_tax_paid_status` remains for Shinhan only. In B, 8 names are renamed.
- Alias map shape, one entry per rename: `{ "template": "tata-capital-title-report", "old": "part3_minor_interest", "canonical": "minor_claims" }`, kept next to the manifests so stored drafts using the old name still load.
- Section C is left alone unless you say otherwise.

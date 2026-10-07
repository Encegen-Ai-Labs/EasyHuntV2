# Bank template prep notes

Status: **all 10 source reports converted** into 9 templates (the two Tata Capital reports share one template). Field names were unified in one pass (merges and renames applied, alias map in `backend/templates/scrutiny_reports/field_aliases.json`); the proposal is in `docs/FIELD_UNIFICATION_PROPOSAL.md`. This file is regenerated from the field manifests.

Templates are docxtpl files in `backend/templates/scrutiny_reports/`, each with a `<name>.fields.json` manifest next to it. Copies of the templates are in `docs/bank-templates-originals/`. Render with `autoescape=True`. Any field that is not supplied renders as empty text.

| Template | Bank | Fields | Loops | must_confirm | glance |
|---|---|---|---|---|---|
| `idfc-first-bank-title-report.docx` | IDFC FIRST Bank | 56 | 5 | 7 | 54 |
| `tata-capital-title-report.docx` | Tata Capital | 37 | 5 | 14 | 28 |
| `kotak-mahindra-bank-title-report.docx` | Kotak Mahindra Bank | 23 | 7 | 10 | 20 |
| `icici-hfc-title-report.docx` | ICICI HFC | 51 | 6 | 23 | 34 |
| `cholamandalam-title-report.docx` | Cholamandalam Investment and Finance | 30 | 7 | 11 | 26 |
| `jio-credit-title-report.docx` | Jio Credit | 55 | 5 | 22 | 38 |
| `indusind-bank-title-report.docx` | IndusInd Bank | 27 | 6 | 9 | 24 |
| `shinhan-bank-title-report.docx` | Shinhan Bank | 80 | 5 | 39 | 46 |
| `hdfc-bank-title-report.docx` | HDFC Bank | 60 | 2 | 26 | 36 |

## Conventions

- **Source of every field** (`source` in the manifests): `extracted` (from case documents), `drafted` (proposed by the system or written by the lawyer, always confirmed by the lawyer), `case_intake` (entered when the case is created or the report issued), `search_office` (from the Sub-Registrar / IGR search), `profile` (the advocate: name, place).
- **Review level** (`review_level` on every field and loop): `must_confirm` is a legal judgement (opinion, marketability, adverse or critical remarks, tenure, SARFAESI enforceability, claims, permissions). It is never auto-confirmed, and the system must not draft "clear and marketable", "no adverse entry", "enforceable" or similar favourable wording for it while the case has open red flags. `glance` is a factual checklist answer, party or search detail that can be pre-filled from extracted documents and shown for a quick lawyer check. No conclusion text is hard-coded in any template.
- `property_tenure` is must_confirm because it selects the ownership wording in the opinion ("are the owners" for Freehold, "have acquired leasehold rights" for Leasehold; any other value prints no ownership clause).
- `NONE` / `NIL` labels are conditional: they print only when the matching list is empty.
- Tick boxes are text checkboxes (☐ / ☒) driven by choice fields. No drawn shapes are used for choices.
- Repeating sections are `{%p for %}` paragraph loops or `{%tr for %}` row loops; each was tested at 0, 1 and larger counts.
- Metadata scrubbed from every template: document author, last editor, created / modified / last-printed dates, and Google Docs custom XML. Letterhead text and image remain in each header.

## Decisions recorded

- **Field names were unified after all templates were done.** Merges (same question in substance) and renames (dropping the Tata-specific `part3_` prefix) were applied; each old name is kept in the alias map so stored drafts still resolve. Seven groups where bank wording may change the meaning were left unchanged and are listed as questions for the lawyer below.
- **Review level per field (`review_level`)** replaces the single `conclusion` flag: `must_confirm` (legal judgement: opinion, marketability, adverse / critical remarks, tenure, SARFAESI enforceability; never auto-confirmed; no positive wording while red flags are open) or `glance` (factual checklist answers that can be pre-filled from extracted documents and shown for a quick lawyer check). Applied to all manifests; `conclusion_fields` is now `must_confirm_fields`. Borderline calls: chain-of-title narration is `glance`; `ulc_status` and `na_conversion_status` are `must_confirm`.
- **"NA order" wording is kept as in the bank form** (Cholamandalam). Possible misreading: "NA" there means Non-Agricultural, not "not applicable".
- **Sample renders** with obviously fake data are produced into `backend/templates/_sample_outputs/` (gitignored) so each template can be opened in Word and compared with the original.

## Decisions needed

- **Letterhead, logo and emblem.** The Flairnetic letterhead (firm name, address, phones, email) and the logo image are in the header of every template, and "FOR Flairnetic Advocates" is fixed text in some signature blocks. The HDFC report carries another advocate's letterhead in the body; it is already profile-driven (advocate_name, advocate_qualification, advocate_designation, advocate_address, advocate_mobile, advocate_email, advocate_district). The black "ADVOCATE" emblem image in that letterhead is kept for now. Still to decide for the Flairnetic letterhead and logo, and for the HDFC emblem: stay fixed, become profile-driven, or be removed.

## Open questions for the lawyer

**Field-name groups left unchanged (all templates).** For each group, tell us whether the bank questions mean the same thing and may share one field.
- Clear and marketable title: `title_marketable_status` (Shinhan q2), `title_clear_marketable_status` (HDFC q7), `title_status` (Tata). HDFC q7 also covers encumbrances and minor / HUF claims; Shinhan q2 also covers the ability to create a valid mortgage. Same question?
- Present owner: `present_owner_names` (Shinhan), `transferor_names` (Tata), `record_owner_name` (IDFC, IndusInd), `land_owner_names` (IDFC). Seller, revenue-record owner and search owner come from different sources. One field or several?
- Local and central laws: `local_central_laws_effect` (IndusInd, Shinhan) vs `local_laws_effect` (Tata). Tata lists agricultural, weaker-section and minority laws; the others list the Land Acquisition and Urban Ceiling Acts.
- Leasehold: `lease_tenure_details` (ICICI, Jio, Shinhan) vs `leasehold_terms_details` (Tata). ICICI and Jio ask for the tenure; Tata and Shinhan ask for lease terms, lessor and NOC.
- Certificate paragraph: `declaration_title_statement` (IDFC) vs `certificate_title_statement` (ICICI, Jio, IndusInd, Shinhan). Same paragraph under a different heading?
- Final opinion: `advocate_final_opinion` (IDFC) vs `opinion_conclusion` (all others). IDFC's is a standalone final paragraph; the others are the tail of the ownership sentence.
- Thirteen-year review: `documents_13_years_scrutinized` (ICICI, Jio) vs `title_history_traced_status` (HDFC). One is scrutiny of originals, the other is tracing the history.

**IDFC FIRST Bank**
- Left in place: an empty black oval shape ('Oval 3') beside the Place line. Is it a seal placeholder, and should it stay?
- Left in place: two 1-pixel EMF pictures in the ownership-status row. Leftovers from the source file - remove?

**Tata Capital**
- The signature block is 'For ____________________' with no advocate name and no Place line, so there is no advocate_name or advocate_place field. Should the blank be replaced by advocate_name?

**Kotak Mahindra Bank**
- CONFIRM WITH THE LAWYER: mapping of the two pre-disbursement lists. 'PRE DISBURSEMENT-' (3 items in the source) -> documents_initial_pre_disbursement; 'Prior to Disbursement' (7 items) -> documents_pre_disbursement.

**ICICI HFC**
- liable_party_names: the 'liability of the intending Borrower/co-Borrower' line listed the same names as the mortgagor, not borrower plus co-applicants. Confirm intent.

**Cholamandalam Investment and Finance**
- Decision: the 'NA order dated ...' wording is kept as in the bank form. Possible misreading: 'NA' means Non-Agricultural here, not 'not applicable', so a reader could take the sentence as saying no order is needed.
- Boundaries were 'NA' in the source; kept as boundary_* fields (optional).
- Co-applicant line can include firms as well as persons; co_borrower_names is free text.

**Jio Credit**
- liable_party_names: as in the ICICI report, the 'liability of the intending Borrower/co-Borrower' line listed the same names as the mortgagor, not borrower plus co-applicants. Confirm intent.
- mortgage_approval_status: the source answer mixed 'N.A.' with a statement that an order is required (reads as contradictory). It is left to the lawyer to word; the template has no fixed text in the answer.
- The 'Name of the Advocate/Searcher' line and the signature name both use advocate_name; the source had the same person in both.

**IndusInd Bank**
- The source form's questions 'Whether local state/municipal laws or central Acts like Land Acquisition Act, Urban Ceiling Act etc. affect the title' is mapped to a new field local_central_laws_effect, not to Tata's part3_local_laws, because the wording differs.
- Co-borrower line can list people who are not mortgagors; co_borrower_names is free text.

**Shinhan Bank**
- Letter number and date of the bank's instruction letter were blank placeholders in the source; kept as optional bank_letter_number / bank_letter_date.
- Question 2 ('absolute, clear and marketable title') and the certificate paragraph are lawyer conclusions; the source answered 'Yes.' with no qualification.

**HDFC Bank**
- SRO search receipt number is 'P-611/08/2026' style; search_receipt_number is free text.

## Ambiguities flagged during conversion

**IDFC FIRST Bank**
- 'As per Banks Policy' (mortgage type row) left as fixed text: it states bank policy, not a property fact.
- Chain-of-title narrative sentences about development agreement, power of attorney and allotment are structural text for builder-project cases; they are not conditional on the case having those steps.
- Tick boxes were drawn shapes carrying the source case's selections; replaced with text checkboxes driven by choice fields.
- Tick boxes are text checkboxes driven by choice fields (borrower_nature, mortgagor_nature, land_revenue_type, property_tenure). An unset choice leaves all boxes unticked.
- The 'Others' box ticks when land_revenue_type_other / property_tenure_other is non-empty.
- Fixed remnants: 'As per Banks Policy' (mortgage type row).
- chain_steps does not exist in this template: the chain narrative uses structured fields plus two nested tables (chain_dev_agreements, chain_allotments).

**Tata Capital**
- Property description is one field (flat-in-tower and leasehold-plot descriptions are structured differently).
- Chain of title is free text, one paragraph per step (no sub-fields).
- The opinion's ownership clause is conditional on property_tenure; everything after it is opinion_conclusion.
- 'Part III' answers that were identical in both source reports were first left fixed by mistake; all 16 are now fields.
- Built from one flat case and tested at a leasehold-plot case's entry counts; one template serves both.

**Kotak Mahindra Bank**
- Property description and chain steps are coarse fields, as in Tata.
- 'PLACE' and the advocate name are fields; the firm name in 'FOR Flairnetic Advocates' is fixed (see letterhead decision).
- documents_post_disbursement: the original had no item paragraphs; one loop block was added.
- The mutation question in the original has no answer line, so no field exists for it.

**ICICI HFC**
- Part V holds 19 question-and-answer lines; every answer is a field.
- 'Name of the Advocate/Searcher' is the advocate_name field.
- documents_verified renders twice (Part II list and Part IV evidence list), so it only needs to be supplied once.
- title_notes renders twice (end of the narration and under REMARKS).
- The original has no Part III heading (jumps from Part II to Part IV); left as is.
- The ownership clause in Part VI only prints for property_tenure Freehold or Leasehold; any other value prints nothing there.
- Bank name is taken from the document ('ICICI HFC Ltd.' / 'ICICI Home Finance'); file named icici-hfc-title-report.

**Cholamandalam Investment and Finance**
- Narration contains two parallel land chains; modelled as a nested loop.
- Same Flairnetic form as the Kotak report. Title narration is two parts: land_chains (one chain per land parcel, each with its own heading and a nested list 'steps') followed by the common chain_steps (construction, RERA, purchase). Each land_chains entry needs heading and steps.
- completion_certificates renders inline on the heading line (joined with spaces), not as a separate paragraph.
- documents_post_disbursement: the original had no item paragraphs; one loop block was added.
- The mutation question in the original has no answer line, so no field exists for it.

**Jio Credit**
- Part V holds 19 question-and-answer lines; every answer is a field (same as ICICI HFC).
- Same firm form as the ICICI HFC report (Part I-VI, 19 question-and-answer lines in Part V); field names reused from ICICI.
- documents_verified renders twice (Part II list and Part IV evidence list), so it only needs to be supplied once.
- Boundaries are separate lines in this form, so boundary_east/south/west/north are fields and property_description excludes them. Each boundary value includes the leading 'By' as written by the lawyer.
- The Part VI ownership clause only prints for property_tenure Freehold or Leasehold; any other value prints nothing there.
- Part III (flow of title) is chain_steps, one paragraph per step; the source has no separate title-notes block.
- Source typos fixed in fixed text: a stray ']]]' before 'Type of Loan' was removed and 'further clarify that that' now reads 'further clarify that'.
- Bank name ('Jio Credit Limited', 'JCL') is fixed text taken from the document; file named jio-credit-title-report.

**IndusInd Bank**
- Same firm form as the Kotak / Chola / ICICI reports, in the IndusInd layout (title opinion and title search report).
- property_description renders twice (subject line and 'Description of the property').
- documents_nice_to_have, documents_at_disbursement and documents_post_disbursement had no item paragraphs in the original (NIL / NONE); one loop block was added to each, and NIL / NONE prints only when the list is empty.
- The two closing statements were fixed text in the source ('the said property is free from all encumbrance ... valid, absolute, clear and marketable title', 'we confirm that the Borrowers ... can create Equitable Mortgage ... enforceability under the SARFAESI Act is secured'). They are now certificate_title_statement, mortgage_confirmation_statement and sarfaesi_conclusion, so no conclusion wording is hard-coded.
- search_conclusion holds the answer to 'Is there any encumbrance as per search'; record_owner_name holds 'Name of the Owners as per search'.
- The 'Manger' typo in the addressee line is left as in the source.
- There is no place or date line under the signature in this form, so there is no advocate_place field.

**Shinhan Bank**
- Different form from the Flairnetic reports: a 39-line bank questionnaire table plus Income Tax, Companies Act and Agricultural Land investigation tables. Every answer cell is a field.
- Table rows are fixed: the question text and numbering stay as in the bank form (the source numbers two rows '18').
- documents_verified is a row loop (Sr. No. is the loop index); documents_pre_disbursement and documents_post_disbursement are paragraph loops inside the answer to the equitable-mortgage question.
- The mortgage_creatable answer replaces the source sentence 'YES - Equitable Mortgage by Deposit of Title Deeds is possible.'; the following line 'The following documents shall be obtained ...' stays fixed.
- The seven numbered certificate points (cert_*) and the closing 'I certify that ...' paragraph were fixed conclusion text in the source and are now fields, so no conclusion wording is hard-coded.
- 'Name of the Title Holder' (top table) uses mortgagor_name (the intending buyers); present_owner_names is the seller, asked in question 1.
- Tax rows 6 and 22(a) both ask about tax: row 6 is property_tax_payment_status, row 22(a) is property_tax_paid_status.
- The source search note reads 'receipt dated <number>'; the wording is kept and the number goes in search_receipt_number.
- The narration had a blank paragraph between the last 'we find' lines; it was removed so chain_steps is one loop.
- documents_examined (the 'I have examined the documents in detail' list) is a separate loop from documents_verified, because the two lists are worded differently in the source.
- The signature block has an 'Adv. {{ advocate_name }}' line added under 'For Flairnetic Advocates' (the source had none).

**HDFC Bank**
- Different advocate's form: title search report (TSR) for agricultural land, with the advocate's own letterhead in the body. The letterhead is now profile fields (advocate_name, advocate_qualification, advocate_designation, advocate_address, advocate_mobile, advocate_email, advocate_district), so no one's personal details are fixed in the template. See the letterhead decision.
- land_parcels is one loop rendered in three places: the boundaries block, the M.E. extract list, and the Khate extract list under documents required before disbursal. Each entry: gat_number, east, west, south, north, mutation_entries. The source heading said 'Gat No. 800' in the boundaries and 'Gat No.800/1' elsewhere; the template prints the one gat_number everywhere.
- title_flows replaces four separate flow-of-title tables with one row loop: each entry has gat_label and a nested list steps, lettered A, B, C ... automatically. The three later tables of the source were merged into the first table's layout.
- Boundaries were two lines per gat in one place and four lines in another; both now print the same structure (East, West, South, North).
- Tenure table rows (a) to (h) are eight separate answer fields (tenure_*); the source answered 'Not applicable' to all but the one that applies.
- 'Statues of owner/s' (source spelling) is mortgagor_nature (choice, same as IDFC).
- The 7/12 extract text, the mortgage-deed line and the post-disbursal line repeat the property description; they use property_description (or seven_twelve_extract_details for the examined-documents row).
- The long checklist answers that carried the same charge sentence several times are separate fields (title_clear_marketable_status, sro_tahsildar_search_status, encumbrance_title_status, final_encumbrance_status), each free text.
- The final remark about which gat was searched at the SRO is remarks.
- The final opinion (all-caps sentence) is opinion_conclusion; the 'Obtain - NOC from ...' instruction is noc_conditions.
- Decision: the advocate letterhead is profile-driven (profile fields). The black 'ADVOCATE' emblem image is kept for now; see the letterhead decision in the notes.

## Loop sections

| Loop | Item fields | Source | Review level | Templates (original entries) |
|---|---|---|---|---|
| `chain_allotments` | agreement_and_poa, allotted_units, allottee | extracted | glance | IDFC (3) |
| `chain_dev_agreements` | area, date_and_reg, party | extracted | glance | IDFC (3) |
| `documents_post_disbursement` | date, description, form, nature | extracted | glance | IDFC (0), TATA (0), KOTAK (0), ICICI (1), CHOLA (0), JIO (5), INDUS (0 (NONE)), SHIN (6) |
| `documents_pre_disbursement` | date, description, form, nature | extracted | glance | IDFC (4), TATA (5 (second: 8)), KOTAK (7), ICICI (5), CHOLA (4), JIO (4), INDUS (4), SHIN (4) |
| `documents_verified` | date, description, form, nature | extracted | glance | IDFC (13), TATA (3 (second source report: 7)), KOTAK (6), ICICI (6), CHOLA (9), JIO (6), INDUS (10), SHIN (7) |
| `chain_steps` | text per entry | drafted | glance | TATA (4 (second: 6)), KOTAK (9), ICICI (6), CHOLA (3), JIO (7), INDUS (10), SHIN (10) |
| `documents_at_disbursement` | description, form | extracted | glance | TATA (0), INDUS (0 (NIL)) |
| `completion_certificates` | text per entry | extracted | glance | KOTAK (1), CHOLA (1) |
| `deviations` | deviation, implications, mitigation | drafted | must_confirm | KOTAK (0 (placeholder row)), CHOLA (0 (placeholder row)) |
| `documents_initial_pre_disbursement` | description | extracted | glance | KOTAK (3) |
| `search_entries` | particulars, year | search_office | glance | ICICI (13 (12 were NIL)), JIO (13 (12 were NIL)) |
| `title_notes` | text per entry | drafted | must_confirm | ICICI (1) |
| `land_chains` | heading | drafted | glance | CHOLA (2 chains x 2 steps each) |
| `documents_nice_to_have` | description | extracted | glance | INDUS (0 (NIL)) |
| `documents_examined` | description | extracted | glance | SHIN (7) |
| `land_parcels` | east, gat_number, mutation_entries, north, south, west | extracted | glance | HDFC (4 gat numbers) |
| `title_flows` | gat_label | drafted | glance | HDFC (4 flows (10 / 13 / 11 / 12 steps)) |

Each loop was rendered at its original count, at a different count, and at 0 / 1 / large counts without errors. Section counts marked "second" refer to the other Tata Capital source report, which the same template also handles.

## Field-name unification (applied)

Merges and renames were applied from `docs/FIELD_UNIFICATION_PROPOSAL.md` (sections A and B). Every old name is in `backend/templates/scrutiny_reports/field_aliases.json` with its template and canonical name; a stored draft that uses an old name must be read as the canonical one.

| Old name | Canonical name | Template | Kind |
|---|---|---|---|
| `mortgage_requirement` | `mortgage_creatable` | cholamandalam-title-report | merge |
| `property_tax_paid_status` | `property_tax_payment_status` | idfc-first-bank-title-report | merge |
| `search_challan_date` | `search_date` | idfc-first-bank-title-report | merge |
| `search_challan_date` | `search_date` | kotak-mahindra-bank-title-report | merge |
| `part3_stamp_duty` | `stamp_duty_status` | shinhan-bank-title-report | merge |
| `part3_conversion_permission` | `na_conversion_status` | tata-capital-title-report | merge |
| `part3_govt_grant` | `govt_grant_status` | tata-capital-title-report | rename |
| `part3_land_use` | `land_use_status` | tata-capital-title-report | rename |
| `part3_leasehold_details` | `leasehold_terms_details` | tata-capital-title-report | rename |
| `part3_litigation` | `litigation_status` | tata-capital-title-report | rename |
| `part3_local_laws` | `local_laws_effect` | tata-capital-title-report | rename |
| `part3_minor_interest` | `minor_claims` | tata-capital-title-report | merge |
| `part3_municipal_limits` | `municipal_limits_status` | tata-capital-title-report | rename |
| `part3_municipal_mutation` | `municipal_mutation_status` | tata-capital-title-report | rename |
| `part3_other_permissions` | `mortgage_approval_status` | tata-capital-title-report | merge |
| `part3_revenue_mutation` | `mutation_extract_status` | tata-capital-title-report | merge |
| `part3_sanctions_reviewed` | `sanctions_reviewed_status` | tata-capital-title-report | rename |
| `part3_sarfaesi_enforceable` | `sarfaesi_conclusion` | tata-capital-title-report | merge |
| `part3_stamp_duty` | `stamp_duty_status` | tata-capital-title-report | merge |
| `part3_taxes_paid` | `property_tax_payment_status` | tata-capital-title-report | merge |

Deliberately not merged: the bank reference numbers (`reference_number`, `application_number`, `los_id`, `webtop_number`), `loan_product` vs `loan_type` / `loan_purpose`, `search_conclusion` vs `search_flow_conclusion`, `property_tenure` vs the HDFC `tenure_*` rows, `boundary_*` vs `land_parcels`. Document loops share names but not item fields (`nature, date, form` in IDFC; `date, description, form` in Shinhan; `description` elsewhere).

## All fields (union across templates)

| Field | Type | Source | Review level | Templates |
|---|---|---|---|---|
| `acquisition_proceedings_status` | text | drafted | must_confirm | HDFC |
| `additional_precautions_status` | text | drafted | must_confirm | SHIN |
| `adivasi_land_status` | text | drafted | must_confirm | ICICI, JIO |
| `adverse_remarks` | text | drafted | must_confirm | KOTAK, CHOLA |
| `advocate_address` | text | profile | glance | HDFC |
| `advocate_designation` | text | profile | glance | HDFC |
| `advocate_district` | text | profile | glance | HDFC |
| `advocate_email` | text | profile | glance | HDFC |
| `advocate_final_opinion` | text | drafted | must_confirm | IDFC |
| `advocate_mobile` | text | profile | glance | HDFC |
| `advocate_name` | text | profile | glance | IDFC, KOTAK, ICICI, CHOLA, JIO, INDUS, SHIN, HDFC |
| `advocate_place` | text | profile | glance | IDFC, KOTAK, ICICI, CHOLA, JIO, HDFC |
| `advocate_qualification` | text | profile | glance | HDFC |
| `agreement_for_sale_registered_status` | text | drafted | glance | SHIN |
| `agri_consolidation_status` | text | drafted | must_confirm | SHIN |
| `agri_hidden_charges_status` | text | drafted | must_confirm | SHIN |
| `agri_inspection_status` | text | drafted | glance | SHIN |
| `agri_khata_shares` | text | drafted | glance | SHIN |
| `agri_mutation_status` | text | drafted | glance | SHIN |
| `agri_self_cultivation_status` | text | drafted | glance | SHIN |
| `agri_surplus_land_status` | text | drafted | must_confirm | SHIN |
| `allotment_letter_date` | date | extracted | glance | IDFC |
| `application_number` | text | case_intake | glance | ICICI, JIO, INDUS |
| `balance_transfer_status` | text | case_intake | glance | INDUS |
| `bank_branch` | text | case_intake | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, SHIN, HDFC |
| `bank_letter_date` | text | case_intake | glance | SHIN |
| `bank_letter_number` | text | case_intake | glance | SHIN |
| `borrower_name` | text | case_intake | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, INDUS, HDFC |
| `borrower_nature` | choice | case_intake | glance | IDFC |
| `boundary_east` | text | extracted | glance | IDFC, CHOLA, JIO |
| `boundary_north` | text | extracted | glance | IDFC, CHOLA, JIO |
| `boundary_south` | text | extracted | glance | IDFC, CHOLA, JIO |
| `boundary_west` | text | extracted | glance | IDFC, CHOLA, JIO |
| `built_up_area_sqft` | number | extracted | glance | IDFC |
| `built_up_area_sqm` | number | extracted | glance | IDFC |
| `buyover_bank_name` | text | case_intake | glance | INDUS |
| `cert_land_reforms_statement` | text | drafted | must_confirm | SHIN |
| `cert_liability_statement` | text | drafted | must_confirm | SHIN |
| `cert_minor_claims_statement` | text | drafted | must_confirm | SHIN |
| `cert_mortgage_availability_statement` | text | drafted | must_confirm | SHIN |
| `cert_prior_mortgage_statement` | text | drafted | must_confirm | SHIN |
| `cert_ulc_statement` | text | drafted | must_confirm | SHIN |
| `cert_undivided_minor_share_statement` | text | drafted | must_confirm | SHIN |
| `certificate_title_statement` | text | drafted | must_confirm | ICICI, JIO, INDUS, SHIN |
| `chain_of_title_status` | text | drafted | must_confirm | HDFC |
| `co_borrower_names` | text | case_intake | glance | TATA, ICICI, CHOLA, JIO, INDUS, HDFC |
| `consenting_party_names` | text | extracted | glance | IDFC |
| `critical_remarks` | text | drafted | must_confirm | TATA |
| `cts_number` | text | extracted | glance | IDFC |
| `declaration_mortgage_statement` | text | drafted | must_confirm | IDFC |
| `declaration_title_statement` | text | drafted | must_confirm | IDFC |
| `deficiencies_status` | text | drafted | must_confirm | INDUS |
| `desirable_documents_post_disbursement` | text | extracted | glance | HDFC |
| `desirable_documents_pre_disbursement` | text | extracted | glance | HDFC |
| `developer_authority_status` | text | drafted | must_confirm | SHIN |
| `developer_name` | text | extracted | glance | IDFC |
| `developer_partners` | text | extracted | glance | IDFC |
| `development_agreement_status` | text | drafted | glance | SHIN |
| `district` | text | extracted | glance | IDFC, HDFC |
| `documents_13_years_scrutinized` | text | drafted | must_confirm | ICICI, JIO |
| `ec_applied_by` | text | search_office | glance | ICICI, JIO |
| `ec_encumbrances` | text | search_office | glance | ICICI, JIO |
| `ec_obtained` | text | search_office | glance | ICICI, JIO |
| `ec_verified_status` | text | extracted | glance | HDFC |
| `ec_years` | text | search_office | glance | ICICI, JIO |
| `encumbrance_free_status` | text | drafted | must_confirm | SHIN |
| `encumbrance_title_status` | text | drafted | must_confirm | HDFC |
| `final_encumbrance_status` | text | drafted | must_confirm | HDFC |
| `final_genuineness_status` | text | drafted | must_confirm | HDFC |
| `final_marketability_status` | text | drafted | must_confirm | HDFC |
| `flat_independent_title_status` | text | drafted | must_confirm | SHIN |
| `flat_numbers` | text | extracted | glance | IDFC |
| `flat_special_enactment_status` | text | drafted | glance | HDFC |
| `flat_undivided_share_status` | text | drafted | glance | HDFC |
| `floor` | text | extracted | glance | IDFC |
| `from_charge_status` | text | extracted | glance | HDFC |
| `gat_numbers` | text | extracted | glance | IDFC |
| `genuineness_checked_status` | text | drafted | must_confirm | HDFC |
| `government_claims` | text | drafted | must_confirm | KOTAK, CHOLA |
| `govt_grant_status` | text | drafted | must_confirm | TATA |
| `independent_title_verification_status` | text | drafted | must_confirm | SHIN |
| `joint_family_property_status` | text | drafted | must_confirm | ICICI, JIO, SHIN |
| `khate_extract_details` | text | extracted | glance | HDFC |
| `land_agricultural_status` | choice | drafted | glance | KOTAK, CHOLA |
| `land_area_sqm` | number | extracted | glance | IDFC |
| `land_owner_names` | text | extracted | glance | IDFC |
| `land_revenue_dues_status` | text | drafted | glance | SHIN |
| `land_revenue_type` | choice | drafted | glance | IDFC |
| `land_revenue_type_other` | text | drafted | glance | IDFC |
| `land_use_status` | text | drafted | glance | TATA |
| `lease_tenure_details` | text | drafted | must_confirm | ICICI, JIO, SHIN |
| `leasehold_terms_details` | text | drafted | must_confirm | TATA |
| `liable_party_names` | text | extracted | glance | ICICI, JIO |
| `litigation_status` | text | drafted | must_confirm | TATA |
| `loan_product` | text | case_intake | glance | TATA |
| `loan_purpose` | text | case_intake | glance | ICICI, JIO, HDFC |
| `loan_type` | text | case_intake | glance | ICICI, JIO |
| `local_authority` | text | extracted | glance | IDFC |
| `local_central_laws_effect` | text | drafted | must_confirm | INDUS, SHIN |
| `local_laws_compliance_status` | text | drafted | must_confirm | SHIN |
| `local_laws_effect` | text | drafted | must_confirm | TATA |
| `lod_verified_status` | text | drafted | glance | INDUS |
| `los_id` | text | case_intake | glance | CHOLA |
| `minor_claims` | text | drafted | must_confirm | TATA, KOTAK, ICICI, CHOLA, JIO, INDUS |
| `missing_documents_status` | text | drafted | must_confirm | HDFC |
| `mortgage_approval_status` | text | drafted | must_confirm | IDFC, TATA, ICICI, JIO, SHIN |
| `mortgage_confirmation_statement` | text | drafted | must_confirm | INDUS |
| `mortgage_creatable` | text | drafted | must_confirm | KOTAK, ICICI, CHOLA, JIO, SHIN, HDFC |
| `mortgage_intimation_status` | text | drafted | glance | IDFC |
| `mortgage_joining_party_names` | text | extracted | glance | SHIN |
| `mortgage_type` | choice | case_intake | glance | TATA, KOTAK, ICICI, CHOLA, JIO, INDUS |
| `mortgagor_name` | text | extracted | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, INDUS, SHIN, HDFC |
| `mortgagor_nature` | choice | case_intake | glance | IDFC, HDFC |
| `municipal_limits_status` | text | drafted | glance | TATA |
| `municipal_mutation_status` | text | drafted | glance | TATA |
| `mutation_extract_status` | text | drafted | glance | IDFC, TATA, SHIN |
| `na_conversion_status` | text | drafted | must_confirm | TATA, ICICI, JIO, SHIN |
| `negative_remarks_status` | text | drafted | must_confirm | INDUS |
| `noc_conditions` | text | drafted | must_confirm | HDFC |
| `occupation_certificate_status` | text | drafted | glance | IDFC, SHIN |
| `opinion_conclusion` | text | drafted | must_confirm | TATA, KOTAK, ICICI, CHOLA, JIO, SHIN, HDFC |
| `original_title_deeds_status` | text | drafted | glance | SHIN |
| `owner_entity_status` | text | drafted | glance | SHIN |
| `personal_law_restriction_status` | text | drafted | must_confirm | SHIN |
| `poa_authority_status` | text | drafted | must_confirm | ICICI, JIO |
| `poa_mortgage_status` | text | drafted | must_confirm | SHIN |
| `poa_registered_status` | text | drafted | must_confirm | ICICI, JIO |
| `poa_transfer_status` | text | drafted | glance | ICICI, JIO |
| `possession_documents_status` | text | drafted | glance | SHIN |
| `present_owner_names` | text | extracted | glance | SHIN |
| `previous_owners_competent` | text | drafted | must_confirm | ICICI, JIO |
| `project_name` | text | extracted | glance | IDFC |
| `promoter_title_status` | text | drafted | must_confirm | SHIN |
| `property_description` | text | extracted | glance | TATA, KOTAK, ICICI, CHOLA, JIO, INDUS, SHIN, HDFC |
| `property_tax_paid_status` | text | drafted | glance | SHIN |
| `property_tax_payment_status` | text | drafted | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, SHIN |
| `property_tenure` | choice | drafted | must_confirm | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, INDUS, SHIN |
| `property_tenure_other` | text | drafted | glance | IDFC |
| `property_type` | text | case_intake | glance | ICICI, JIO, INDUS, SHIN |
| `purchaser_name` | text | extracted | glance | IDFC |
| `record_owner_name` | text | extracted | glance | IDFC, INDUS |
| `reference_number` | text | case_intake | glance | IDFC, TATA, SHIN |
| `remarks` | text | drafted | must_confirm | ICICI, JIO, HDFC |
| `report_date` | date | case_intake | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, INDUS, SHIN, HDFC |
| `required_documents_available` | text | drafted | glance | ICICI, JIO |
| `rera_certificate_date` | date | extracted | glance | IDFC |
| `rera_number` | text | extracted | glance | IDFC |
| `rera_validity_expiry_date` | date | extracted | glance | IDFC |
| `reservations_status` | text | drafted | must_confirm | ICICI, JIO |
| `revenue_flow_scrutiny_status` | text | drafted | must_confirm | HDFC |
| `revenue_search_date` | date | search_office | glance | HDFC |
| `revenue_search_years` | number | search_office | glance | HDFC |
| `revenue_tenancy_effect` | text | drafted | must_confirm | ICICI, JIO, SHIN |
| `roc_charge_dates_nature` | text | drafted | glance | SHIN |
| `roc_charge_modifications` | text | drafted | glance | SHIN |
| `roc_charge_satisfaction` | text | drafted | glance | SHIN |
| `roc_charges_subsisting` | text | drafted | must_confirm | SHIN |
| `roc_debentures_status` | text | drafted | must_confirm | SHIN |
| `roc_receiver_status` | text | drafted | must_confirm | SHIN |
| `roc_scheme_proceedings_status` | text | drafted | must_confirm | SHIN |
| `roc_search_status` | text | extracted | glance | HDFC |
| `sale_permission_status` | text | drafted | must_confirm | ICICI, JIO |
| `sanctions_required` | text | drafted | must_confirm | KOTAK, CHOLA |
| `sanctions_reviewed_status` | text | drafted | must_confirm | TATA |
| `sarfaesi_conclusion` | text | drafted | must_confirm | TATA, KOTAK, ICICI, CHOLA, JIO, INDUS |
| `search_challan_number` | text | search_office | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, INDUS, SHIN |
| `search_conclusion` | text | drafted | must_confirm | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, INDUS |
| `search_date` | date | search_office | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, INDUS, HDFC |
| `search_flow_conclusion` | text | drafted | must_confirm | ICICI, CHOLA, JIO |
| `search_period_from_year` | number | search_office | glance | IDFC, TATA, ICICI, JIO, INDUS, SHIN |
| `search_period_to_year` | number | search_office | glance | IDFC, TATA, ICICI, JIO, INDUS, SHIN |
| `search_period_years` | number | search_office | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, INDUS, SHIN, HDFC |
| `search_receipt_number` | text | search_office | glance | IDFC, TATA, KOTAK, ICICI, CHOLA, JIO, SHIN, HDFC |
| `search_report_obtained` | text | search_office | glance | ICICI, JIO |
| `seven_twelve_extract_details` | text | extracted | glance | HDFC |
| `share_certificate_status` | text | drafted | glance | SHIN |
| `society_conveyance_status` | text | drafted | glance | SHIN |
| `society_lien_requirement_status` | text | drafted | glance | SHIN |
| `society_membership_status` | text | drafted | glance | SHIN |
| `society_noc_status` | text | drafted | glance | SHIN |
| `special_comments` | text | drafted | must_confirm | HDFC |
| `sro_scrutiny_status` | text | drafted | must_confirm | HDFC |
| `sro_tahsildar_search_status` | text | drafted | must_confirm | HDFC |
| `stamp_duty_status` | text | drafted | glance | TATA, SHIN |
| `sub_registrar_office` | text | search_office | glance | IDFC, ICICI, JIO, HDFC |
| `taluka` | text | extracted | glance | IDFC, HDFC |
| `tax_acquisition_proceedings_status` | text | drafted | must_confirm | SHIN |
| `tax_prior_permission_status` | text | drafted | must_confirm | SHIN |
| `tax_receipt_perused_status` | text | drafted | glance | SHIN |
| `tax_recovery_action_status` | text | drafted | must_confirm | SHIN |
| `tenure_acquisition_status` | text | drafted | must_confirm | HDFC |
| `tenure_company` | text | drafted | must_confirm | HDFC |
| `tenure_freehold_govt` | text | drafted | must_confirm | HDFC |
| `tenure_freehold_private` | text | drafted | must_confirm | HDFC |
| `tenure_govt_land` | text | drafted | must_confirm | HDFC |
| `tenure_huf` | text | drafted | must_confirm | HDFC |
| `tenure_leasehold_govt_agency` | text | drafted | must_confirm | HDFC |
| `tenure_leasehold_private` | text | drafted | must_confirm | HDFC |
| `title_clear_marketable_status` | text | drafted | must_confirm | HDFC |
| `title_history_traced_status` | text | drafted | must_confirm | HDFC |
| `title_marketable_status` | text | drafted | must_confirm | SHIN |
| `title_nature` | text | drafted | must_confirm | SHIN |
| `title_status` | text | drafted | must_confirm | TATA |
| `transferor_names` | text | extracted | glance | TATA |
| `ulc_status` | text | drafted | must_confirm | IDFC, ICICI, JIO, SHIN |
| `undivided_share_transfer_status` | text | drafted | glance | SHIN |
| `village` | text | extracted | glance | IDFC, HDFC |
| `webtop_number` | text | case_intake | glance | TATA |

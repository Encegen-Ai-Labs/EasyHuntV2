# EasyHuntV2: Standard Operating Procedure

AI-assisted property title scrutiny for Indian banks.
Encegen AI Labs, internal document.

---

## 1. Purpose

EasyHuntV2 automates the property title scrutiny work that lawyers carry out for Indian banks. It turns raw property documents into bank-ready scrutiny reports, with the ownership chain, key parties, and red flags clearly laid out.

---

## 2. Who is involved

| Role | Description |
|---|---|
| Borrower | A person applying to a bank for a home or property loan. Submits their property documents to the bank as part of the application. |
| Bank | Cannot approve a property loan without knowing the title is clean. Sends the borrower's documents to an empanelled lawyer for scrutiny, and needs the result back in its own specific report format. |
| Lawyer | A legal professional specialising in property matters. Verifies ownership history, identifies disputes, and produces the scrutiny report in the bank's required format. The only person who logs into and operates EasyHuntV2. |

---

## 3. Why this exists

Today the lawyer reads every document manually. Many are handwritten, many are in a regional language. The lawyer traces ownership by hand across decades of records, then retypes the findings into whichever format that particular bank demands. It is slow, repetitive, and error-prone.

EasyHuntV2 does the reading, extraction, and formatting so the lawyer spends their time on judgement rather than transcription.

---

## 4. Documents handled

Property documents submitted by the borrower through the bank, including but not limited to:

- 7/12 extract
- Ferfar (mutation records)
- Sale deeds
- Partition deeds
- Gift deeds
- Tax receipts
- Encumbrance certificates
- Any other document establishing ownership, transfer, or encumbrance

Multiple documents belong to a single case. A case represents one property under scrutiny.

---

## 5. System flow

### Step 1: Case creation
The lawyer creates a case in EasyHuntV2 for the property being scrutinised.

### Step 2: Document upload
The lawyer uploads all documents relating to that case together, in a batch, rather than one at a time.

### Step 3: Image enhancement
Every uploaded document is pre-processed to improve legibility before any reading takes place. This covers deskewing, contrast correction, noise reduction and similar, so that whichever engine reads it next has the clearest possible input.

### Step 4: Routing between OCR and VLM/LLM
Documents that are typed or printed go through OCR, which is fast, cheap and reliable on clean machine text.

Documents that are substantially handwritten, or where OCR confidence is low, are routed to the VLM/LLM, which handles messy handwriting and regional scripts far better than OCR can.

The LLM acts as the brain across the whole process, not only as a fallback reader.

### Step 5: Extraction
From the document content the system extracts:

- Names of current and previous owners
- Dates of each transaction
- Survey and plot numbers
- Property location and boundaries
- The nature of each transfer (sale, inheritance, gift, partition)
- The full chain of ownership: who held the property, in what order
- Disputes, litigation, encumbrances, and any other red flags affecting title

### Step 6: Handwriting confirmation
Where handwritten content was detected, the document is flagged for the lawyer to verify, regardless of how confident the system is. Handwritten material is never accepted without human eyes on it.

### Step 7: Translation
Extracted content is made available in both the original language of the document and in English. The lawyer can work in either, and the final report can be produced in the language the bank expects.

### Step 8: Lawyer review and selection
The lawyer reviews the extracted data, corrects anything wrong, and selects the specific text and findings to carry into the report. Nothing reaches the report without the lawyer choosing it.

### Step 9: Report format selection
The lawyer picks the required bank's scrutiny report format from a dropdown. The system holds 12 bank formats as templates.

### Step 10: Report generation
The chosen template, which contains placeholder names and details, is populated with the real extracted and lawyer-approved data from the case documents. The output is a scrutiny report in exactly the format that bank expects to receive.

### Step 11: Export and delivery
The completed report is exported and sent to the bank, which can read it in its own familiar format and make its lending decision.

---

## 6. Role of the LLM

The LLM is not a generic text extractor in this system. It is expected to operate with the knowledge and judgement of a property lawyer:

- Understand Indian property document types and what each one establishes
- Recognise what constitutes a break or gap in a chain of ownership
- Identify what legally counts as a red flag on a title
- Understand the significance of a mutation entry, an encumbrance, a partition
- Use legal terminology correctly and precisely, as a lawyer would

Its output is always a draft for a qualified lawyer to verify and approve. It never issues a final legal opinion on its own.

---

## 7. Core operating principles

- The lawyer is the only user. There is no borrower or bank login.
- Nothing goes into a report without the lawyer selecting or approving it.
- Handwritten content is always flagged for human verification.
- The system assists judgement, it does not replace it.
- Reports must match the receiving bank's format exactly. That is the entire purpose of holding 12 templates.
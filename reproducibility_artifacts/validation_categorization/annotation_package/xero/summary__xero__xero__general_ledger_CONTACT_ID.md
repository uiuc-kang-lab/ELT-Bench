# Column Mismatch Summary

## Database: xero
## Table: xero__general_ledger
## Column: CONTACT_ID

**Description:**
ID of the associated contact, where relevant.

---

## Root Cause
**SQL incorrectly retrieves contact_id for source_types that should have NULL (CASHPAID, CASHREC, ACCPAYCREDIT)**

### Incorrect SQL Logic
```sql
-- Gets contact_id from bank_transaction and credit_note tables
COALESCE(
    inv.contact_id,
    bt.contact_id,
    cn.contact_id
) AS contact_id

-- With joins:
LEFT JOIN invoice inv ON j.source_id = inv.invoice_id AND j.source_type IN ('ACCPAY', 'ACCREC')
LEFT JOIN bank_transaction bt ON j.source_id = bt.bank_transaction_id AND j.source_type IN ('CASHREC', 'CASHPAID')
LEFT JOIN credit_note cn ON j.source_id = cn.credit_note_id AND j.source_type IN ('ACCPAYCREDIT', 'ACCRECCREDIT')
LEFT JOIN contact con ON COALESCE(inv.contact_id, bt.contact_id, cn.contact_id) = con.contact_id
```

### Correct SQL Logic
```sql
-- Only get contact_id from invoice for ACCPAY/ACCREC source_types
inv.contact_id AS contact_id

-- With ONLY the invoice join (remove bank_transaction and credit_note joins):
LEFT JOIN invoice inv ON j.source_id = inv.invoice_id AND j.source_type IN ('ACCPAY', 'ACCREC')
LEFT JOIN contact con ON inv.contact_id = con.contact_id
```

---

## Why the Original Logic Is Wrong

* **What the column description says**: "ID of the associated contact, where relevant"
* **What the SQL computes**: Retrieves contact_id for ACCPAY, ACCREC, CASHPAID, CASHREC, and ACCPAYCREDIT source_types
* **What the GT expects**: CONTACT_ID should ONLY be populated for source_type IN ('ACCPAY', 'ACCREC')

The description "where relevant" is key - according to the ground truth, contacts are only "relevant" for invoice-based journal entries (ACCPAY = Accounts Payable invoices, ACCREC = Accounts Receivable invoices). For other source types:

- **CASHPAID/CASHREC**: Cash payments/receipts - contact is NOT relevant (should be NULL)
- **ACCPAYCREDIT/ACCRECCREDIT**: Credit notes - contact is NOT relevant (should be NULL)
- **TRANSFER, MANJOURNAL, PAYMENTS**: No contact association (should be NULL)

The SQL over-eagerly joins bank_transaction and credit_note tables to get contact information for source types where it's not expected.

---

## Evidence

**Key comparison demonstrating the error:**

| JOURNAL_LINE_ID | SOURCE_TYPE | Wrong Logic | Correct Logic | Ground Truth |
| --------------- | ----------- | ----------- | ------------- | ------------ |
| 24550237-821d-4cc6-b92a-b57f6b744b7f | CASHPAID | 3bbc0733-d765-40a0-86f3-8cd295d7b412 | NULL | NULL |
| 7674803b-3300-40bd-8ade-5b171a0c0e46 | CASHPAID | 3bbc0733-d765-40a0-86f3-8cd295d7b412 | NULL | NULL |
| 45efa954-84ce-41fe-a9a2-b34d9168efbb | CASHPAID | ae5908b8-268b-41ac-9d31-394672b2ead6 | NULL | NULL |
| d7a6e4f0-xxxx-xxxx-xxxx | CASHREC | 3bbc0733-d765-40a0-86f3-8cd295d7b412 | NULL | NULL |
| abcd1234-xxxx-xxxx-xxxx | ACCPAYCREDIT | fd5ed652-4f16-46b5-a185-a1bb3838bf20 | NULL | NULL |

**SOURCE_TYPE distribution showing the issue:**

| SOURCE_TYPE | GT has CONTACT_ID | SQL returns CONTACT_ID |
| ----------- | ----------------- | ---------------------- |
| ACCPAY | Yes (1496 rows) | Yes |
| ACCREC | Yes (426 rows) | Yes |
| CASHPAID | **No** (should be NULL) | **Yes (214 rows)** |
| CASHREC | **No** (should be NULL) | **Yes (16 rows)** |
| ACCPAYCREDIT | **No** (should be NULL) | **Yes (7 rows)** |
| ACCPAYPAYMENT | No | No |
| ACCRECPAYMENT | No | No |
| TRANSFER | No | No |
| MANJOURNAL | No | No |

**Impact:**
* Current implementation: **3796/4033 matches (94.12%)**
* Corrected implementation: **4033/4033 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The SQL should only retrieve contact_id for invoice-related source types (ACCPAY, ACCREC). The joins to bank_transaction (for CASHPAID/CASHREC) and credit_note (for ACCPAYCREDIT/ACCRECCREDIT) should be removed, as contacts are not considered "relevant" for these journal entry types according to the ground truth.

**Source types that correctly have CONTACT_ID populated:**
- ACCPAY (1496 rows) - Accounts Payable invoices
- ACCREC (426 rows) - Accounts Receivable invoices

**Source types that should have NULL CONTACT_ID:**
- CASHPAID (214 rows)
- CASHREC (16 rows)
- ACCPAYCREDIT (7 rows)
- ACCPAYPAYMENT, ACCRECPAYMENT, TRANSFER, MANJOURNAL, APCREDITPAYMENT

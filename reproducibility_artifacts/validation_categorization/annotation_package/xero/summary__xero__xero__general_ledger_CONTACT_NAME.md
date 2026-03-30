# Column Mismatch Summary

## Database: xero
## Table: xero__general_ledger
## Column: CONTACT_NAME

**Description:**
Name of the associated contact, where relevant.

---

## Root Cause
**SQL incorrectly retrieves contact_name for source_types that should have NULL (CASHPAID, CASHREC, ACCPAYCREDIT)**

### Incorrect SQL Logic
```sql
-- Gets contact_name via COALESCE of contact_ids from multiple source tables
con.name AS contact_name

-- Where contact is joined via:
LEFT JOIN contact con ON COALESCE(inv.contact_id, bt.contact_id, cn.contact_id) = con.contact_id

-- And the source tables are:
LEFT JOIN bank_transaction bt ON j.source_id = bt.bank_transaction_id AND j.source_type IN ('CASHREC', 'CASHPAID')
LEFT JOIN credit_note cn ON j.source_id = cn.credit_note_id AND j.source_type IN ('ACCPAYCREDIT', 'ACCRECCREDIT')
```

### Correct SQL Logic
```sql
-- Only get contact_name from invoice-based contacts for ACCPAY/ACCREC source_types
con.name AS contact_name

-- With ONLY the invoice join (remove bank_transaction and credit_note joins):
LEFT JOIN invoice inv ON j.source_id = inv.invoice_id AND j.source_type IN ('ACCPAY', 'ACCREC')
LEFT JOIN contact con ON inv.contact_id = con.contact_id
```

---

## Why the Original Logic Is Wrong

* **What the column description says**: "Name of the associated contact, where relevant"
* **What the SQL computes**: Retrieves contact_name for ACCPAY, ACCREC, CASHPAID, CASHREC, and ACCPAYCREDIT source_types
* **What the GT expects**: CONTACT_NAME should ONLY be populated for source_type IN ('ACCPAY', 'ACCREC')

This column has the same root cause as CONTACT_ID - the description "where relevant" means contacts are only relevant for invoice-based journal entries. The SQL over-eagerly retrieves contact names for bank transactions and credit notes where they should be NULL.

---

## Evidence

**Key comparison demonstrating the error:**

| JOURNAL_LINE_ID | SOURCE_TYPE | Wrong Logic | Correct Logic | Ground Truth |
| --------------- | ----------- | ----------- | ------------- | ------------ |
| 24550237-821d-4cc6-b92a-b57f6b744b7f | CASHPAID | auagZ02LBDUvzR4sWgQgTw== | NULL | NULL |
| 7674803b-3300-40bd-8ade-5b171a0c0e46 | CASHPAID | auagZ02LBDUvzR4sWgQgTw== | NULL | NULL |
| 45efa954-84ce-41fe-a9a2-b34d9168efbb | CASHPAID | wP0Z5ZmN4RKwuMHeZHIdog== | NULL | NULL |
| edab74f6-3037-4c00-ac61-7a673d33f09b | CASHPAID | wP0Z5ZmN4RKwuMHeZHIdog== | NULL | NULL |
| b549f38d-b726-4697-9559-0925e184c540 | CASHPAID | auagZ02LBDUvzR4sWgQgTw== | NULL | NULL |

Note: Contact names appear to be base64-encoded/hashed for privacy.

**Mismatch distribution by SOURCE_TYPE:**

| SOURCE_TYPE | Mismatches (GT=NULL, SQL=value) |
| ----------- | ------------------------------- |
| CASHPAID | 214 |
| CASHREC | 16 |
| ACCPAYCREDIT | 7 |
| **Total** | **237** |

**Impact:**
* Current implementation: **3796/4033 matches (94.12%)**
* Corrected implementation: **4033/4033 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The CONTACT_NAME column follows the same logic as CONTACT_ID - it derives from the contact table via the contact_id join. Since the root cause is the same (incorrect joins to bank_transaction and credit_note tables), fixing the CONTACT_ID logic automatically fixes CONTACT_NAME as well.

**Source types that correctly have CONTACT_NAME populated:**
- ACCPAY (1496 rows) - Accounts Payable invoices
- ACCREC (426 rows) - Accounts Receivable invoices

**Source types that should have NULL CONTACT_NAME:**
- CASHPAID (214 rows)
- CASHREC (16 rows)
- ACCPAYCREDIT (7 rows)
- All other source types (ACCPAYPAYMENT, ACCRECPAYMENT, TRANSFER, MANJOURNAL, APCREDITPAYMENT)

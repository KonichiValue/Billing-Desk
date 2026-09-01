# KRA-007 BILLINGSTATEMENT field mapping notes

Companion to `kra007-billingstatement-mapping.csv`.

Mapping target: leaf fields of `ShinsunaPrinterContext` as emitted by `attrs.asdict` (JSON keys match dataclass attribute names; no renames/aliases). Nested under message template vars as `shinsuna_print` when the print partner file is built.

Source layers (read-only from `~/Projects/kraken-core`):

- Intermediate labels: `.../billing_statement/_dataclasses.py` and `.../common/dataclasses.py`
- Population: `.../billing_statement/context.py`, `_notice.py`
- Print formatting: `.../billing_statement/printer/process.py`, `printer/_dataclasses.py`

## Which revision the line numbers point at

The `evidence` column in both `*-mapping.csv` files cites `path:line`, and
`kraken-core` moves, so a line number only means something against the checkout
it was read from. That was `origin/master` at:

```
488238ecf25a1dfd8b824383aa7542e4e9384ac6   2026-08-28
```

Resolve a citation against that commit rather than against the working copy:

```
git -C ~/Projects/kraken-core show 488238ecf25a:<path> | sed -n '<line>p'
```

Checked on 2026-09-01, against that commit:

| File | Rows | Line spans | Cite a real file and line | Field found in a cited window |
| --- | ---: | ---: | ---: | ---: |
| `kra007-billingstatement-mapping.csv` | 144 | 304 | all | 142 / 144 |
| `paymentslip-mapping.csv` | 59 | 228 | all | 59 / 59 |

The two billing statement rows that do not match are imprecise rather than
wrong. `postal_address_line_6` cites `common/dataclasses.py:45` where the field
is declared five lines below, in the same dataclass; `postal_customer_name`
cites the lines that assign the value through `get_addressee` rather than the
line declaring the field.

Two rows are the exception and say so in their own `evidence`. The
`credit_contexts[].note` and `credit_contexts[].show_positive_amount` fields did
not exist on 28 Aug, so they are cited against master at `fcf2b98f167b`
(2026-09-01) instead.

Run against the working copy on 2026-09-01 instead, the same check passed only
118 of 144, because `context.py` had gained 59 lines in the four days since. That
gap is drift and not error, and it is why this section exists. Expect it to
widen, and pin the commit rather than trusting a line number in a fresh
checkout.

## Totals

| Metric | Count |
| --- | ---: |
| Leaf fields (CSV data rows) | 146 |
| UNRESOLVED | 0 |

## Per-block leaf counts

| Block | Leaves | Notes |
| --- | ---: | --- |
| `customer_context` | 10 | Includes nested `billing_address_context` (8 fields) |
| `billing_document_context` | 3 | |
| `gas_consumption_contexts[]` | 26 | List, one per gas `AccountCharge`; includes `discounts[]` |
| `gas_rate_context` | 4 | Null when no gas |
| `next_month_gas_rate_context` | 24 | Six optional tiers A–F × 4 fields; null when no gas or final reading |
| `gas_reversing_credit_contexts[]` | 4 | List, one per reversing gas credit |
| `electricity_consumption_contexts[]` | 21 | List, one per elec charge; includes parallel `consumption_charges[]` and `consumption_charge_contexts[]` |
| `electricity_reversing_credit_contexts[]` | 4 | |
| `billing_totals_context` | 5 | |
| `supply_point_context` | 9 | Includes nested postal address (7 fields) |
| `payment_context` | 3 | Intermediate also has `payment_method_title`; printer omits it |
| `printing_fee_context` | 11 | Null when no printing-fee charges. `charges[]` never sets note/transaction_date on this branch, but `attrs.asdict` emits both as null, so they are leaves |
| `notice_contexts[]` | 3 | |
| `charge_contexts[]` | 9 | Printer merges ancillary + other + late-payment fees |
| `credit_contexts[]` | 10 | Printer merges ancillary + other (non-reversing), and since 2026-09-01 also late payment fee reversals, which brought `note` and `show_positive_amount` with them |

## Kind breakdown

| kind | count |
| --- | ---: |
| `table` | 39 |
| `derived` | 74 |
| `chain` | 13 |
| `constant` | 6 |
| `enum` | 12 |
| `external` | 2 |

## UNRESOLVED

None. Every leaf was traced to a population site in `context.py` / `_notice.py` and a format site in `printer/process.py` (or passthrough).

## Surprises for a TG reader

1. **Constants, not stored data.** `gas_type` is always `13A 45メガジュール`. `template_id` is always `*`. `gas_consumption_charge_unit` is always `/㎥`. `company_code` prefix/suffix are hardcoded `999B0` / `kraken1002`.

2. **Product names are alias maps, not `Product.display_name`.** Elec and gas use `PRODUCT_NAME_ALIASES` keyed by product code (gas may append addon band).

3. **Elec `reading_end` is `end_at - 1 day`.** Display-inclusive period; `billed_at` for elec-only therefore uses `reading_date`, not `reading_end`.

4. **Meter index / SPIN strings are unhyphenated in this JSON.** Intermediate context has hyphenated properties for PDF, but Shinsuna printer emits `meter_number_str` / `spin_str` raw.

5. **Notices are code-held.** `NoticeEnumMap` has no DB table. Subsidy amounts do come from `MetiCreditPeriod` tables when a subsidy notice is built, but the message templates and priorities do not.

6. **TG-originated metadata on ancillaries.** `charge_contexts[].transaction_date` and `credit_contexts[].transaction_date` for ancillary items are read from `AccountCharge`/`AccountCredit` `.metadata.data["transaction_date"]` (and tax_rate similarly), then reformatted to `YYYY年M月D日`.

7. **Payer address path.** With payer-address consent/campaign, billing name and address come from TG Payments addressee details, not `Account.billing_*`.

8. **Printer merges lists.** Ancillary charges/credits are separate on `StatementContext` but concatenated into `charge_contexts` / `credit_contexts` for Shinsuna. `payment_method_title` never reaches the JSON.

9. **Decimal rules differ by field.** Yen totals: `ROUND_DOWN` to integer. Standing/consumption rates and many elec lines: always 2 decimal places. Mixed amounts: `_format_decimal` (integral as int, else normalize).

## Integration tests (JSON / printer shape)

Under `src/tests/integration/clients/tokyogas/plugins/clients/tokyogas/comms/message_types/billing_statement/`:

| File | What it covers |
| --- | --- |
| `printer/test_process.py` | Builds `get_shinsuna_printer_context`, asserts `attrs.asdict` keys/values for dual-fuel, elec-only, multi-period, ancillary charges/credits: the closest assertion of the emitted Shinsuna JSON shape. |
| `test_context.py` | Unit-style integration of `context.generate` pieces: gas/elec consumption, shutoff flags, discounts, totals, reversing credits, payment, stepped/TOU charge labels. Does not dump printer JSON. |
| `test_message_type.py` | End-to-end billing statement message: builds full statement (print + email paths), payer consent, subsidy, meter replacement/resumption, print gating. Asserts message/template behaviour rather than every `shinsuna_print` leaf. |

Related (not in the three above): `test_notice.py` covers subsidy notice formatting only.

# Data protection impact assessment: DineMate staff recognition

Shop: [__ name] · prepared by [__ name] · date [__ date] · next review [__ date] · not legal advice, review locally before use

## 1. What and why

| Question                           | Answer                                                                                                                                                            |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| What are we turning on?            | Table and queue counting for customers (anonymous); recognition of consented staff in work areas by face template or badge; till CSV import linked to till codes. |
| What problem does it solve?        | [__ for example: counter left empty at lunch, long queues, uneven workload]                                                                                       |
| Could we do it with less data?     | [__ for example: badges instead of faces; counter coverage without names]                                                                                         |
| Is it necessary and proportionate? | [__]                                                                                                                                                              |

## 2. Data

| Data                                     | About whom                        | Source          | Where it is kept | How long                         |
| ---------------------------------------- | --------------------------------- | --------------- | ---------------- | -------------------------------- |
| Table and queue counts                   | Customers, anonymous              | Camera computer | Shop server      | [__ 90] days (Settings)          |
| Face template (128 numbers, encrypted)   | Consented staff who chose face    | Enrol tool      | Shop server only | Until withdrawal or removal      |
| Badge code                               | Consented staff who chose badge   | Owner           | Shop server      | While employed                   |
| Time in work areas                       | Consented staff                   | Camera computer | Shop server      | [__ 60] days (Privacy & consent) |
| Till orders and items, by till code      | Staff (by code), no customer data | Till CSV        | Shop server      | [__]                             |
| Consent record and audit of report views | Staff, owner                      | Dashboard       | Shop server      | [__]                             |

Video and photos: **not stored**. Live view frames stay in memory, with customer faces blurred.

## 3. Lawful basis and consent

- Basis for staff recognition: [__ consent, and whether another basis applies locally]
- How consent is given and recorded: signed form, version and date recorded in the dashboard.
- How a worker withdraws: [__ who they tell]; the owner presses **Withdraw consent**, which deletes the template and history.
- How we make sure saying no has no effect on the job: [__]

## 4. Risks and controls

| Risk                                               | Likelihood | Impact | Controls in the product                                                                                                 | Extra controls here                              |
| -------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| A customer is identified                           | Low        | High   | Matching only inside work areas and only against consented staff; customer faces blurred in live view; no images stored | [__ keep work areas tight to behind the counter] |
| Wrong person named                                 | Medium     | Medium | Name only after 3 consistent matches; dropped after misses or when leaving the area; badge fallback                     | [__ check the sheet with the worker]             |
| Staff data used for discipline it wasn't meant for | [__]       | High   | Owner-only report; every view audited                                                                                   | [__ written policy]                              |
| Template stolen                                    | Low        | Medium | Encrypted at rest; never on cloud servers; deleted on withdrawal                                                        | [__ who holds the server and the key]            |
| Live view seen by the wrong person                 | Low        | Medium | Shop network only; 60 s signed link; owner and manager roles only                                                       | [__ guest Wi-Fi kept separate]                   |
| Data kept too long                                 | Medium     | Low    | Automatic deletion after the retention period                                                                           | [__ yearly review]                               |

## 5. Sign-off

|                               | Name | Date |
| ----------------------------- | ---- | ---- |
| Owner                         |      |      |
| Staff representative (if any) |      |      |
| Reviewer                      |      |      |

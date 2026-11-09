# DineMate Business privacy kit

Templates for a café or restaurant that turns on staff recognition in DineMate Business. Fill in every `[__]` before use.

> **Not legal advice.** These are starting points written for the product's defaults. Review them locally, for example against Sri Lanka's Personal Data Protection Act, No. 9 of 2022, with someone qualified, and change them to match how your shop really works.

| File                                     | Use it for                                                                                       |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------ |
| [staff-notice.md](staff-notice.md)       | The notice every worker reads before anything is turned on. Put a copy on the staff noticeboard. |
| [consent-form.md](consent-form.md)       | The signed opt-in. Record the version and date in **Privacy & consent**; keep the paper copy.    |
| [dpia-template.md](dpia-template.md)     | A data protection impact assessment to complete before go-live and review each year.             |
| [retention-guide.md](retention-guide.md) | What DineMate keeps, for how long, and where to change it.                                       |

## What the product does by default

- **Customers are never identified.** Recognition only runs on people standing inside a marked work area (counter, kitchen, floor), and only compares them with workers who signed consent. Customer faces are blurred in the live view.
- **No video or photos are stored.** Frames stay in the camera computer's memory. The live view is streamed on the shop network only, through a link that expires after 60 seconds.
- **Face templates, not photos.** Enrolment turns five camera shots into one list of 128 numbers. It is encrypted on the shop's own server and refused by cloud servers. Badges are the alternative for anyone who prefers them.
- **Owner-only staff report.** Managers see sales and cameras but not the staff report. Every view of a staff report or worker sheet is recorded and listed under **Who viewed staff reports**.
- **One step to leave.** Withdrawing consent deletes the worker's face template and their time-in-area history at once. Removing a worker also unlinks their till orders, which stay as anonymous sales.
- **Short retention.** Staff time records are deleted after 60 days by default (7 to 365, set by the owner).

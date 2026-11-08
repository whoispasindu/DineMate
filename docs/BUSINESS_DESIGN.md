# DineMate Business — design

Design for the business app (`apps/business`, Phases 8–10). Designed in Figma first; build only after the owner approves it. Figma file: page "DineMate Business v1 — for review" (campus redesign is on "Redesign v4 — final for review").

## Look

Same design language as the campus apps: Bricolage Grotesque for headings and big numbers, DM Sans for everything else, JetBrains Mono for clocks and colour codes only. Raised cards and buttons (a solid darker edge under them), occupancy bars, and the small isometric table scene. Sentence-case labels, text 12 px or larger. Professional and calm: navy carries the app, coral is rare.

| Token | Hex       | Use                                                           |
| ----- | --------- | ------------------------------------------------------------- |
| Navy  | `#14213D` | Main colour: sidebar, headings, seated tables, primary button |
| Deep  | `#0B1528` | Raised edge under navy cards and buttons                      |
| Cream | `#F4EDE0` | Page background                                               |
| Card  | `#FCF8F1` | Panels and cards                                              |
| Coral | `#FF6B5B` | Live, likely free soon, active nav, the one key action        |
| Teal  | `#2F7D68` | Free tables, good numbers                                     |
| Amber | `#B07A12` | Held tables (bag on a seat)                                   |
| Brick | `#B23A2A` | Needs attention: unstaffed counter, long queue                |
| Muted | `#555B69` | Secondary text                                                |
| Line  | `#E4DACA` | Borders and dividers                                          |

No purple in the business app.

## Table states

| State            | Look                                    |
| ---------------- | --------------------------------------- |
| Free             | Teal outline on pale teal, "4 seats"    |
| Seated           | Navy, party size and time seated        |
| Likely free soon | Navy with a coral ring, "~5–10 min"     |
| Held by a bag    | Amber stripes, time held                |
| Needs clearing   | Dashed grey outline, time since leaving |

## Screens

Left navigation on laptop and tablet: Live floor, Customers, Staff, Sales, Reports, Cameras, Privacy & consent, Settings. Venue switcher at the top, server status at the bottom. Every page is reachable in one click.

- **Live floor:** table map with states and timers, tables free now, guests seated, average stay, counter staffing; "Freeing up soon" list and "Needs attention" (clear a table, held tables).
- **Customers:** anonymous visits, average stay, table turns, stay after paying (matched to till orders), visits by hour, stay by table.
- **Staff (owner only):** counter coverage and gaps, items served from the till, serve time, time per work area per worker, how each worker is recognised.
- **Privacy & consent:** staff consent list (face or badge, enrol, view data, remove), what is kept and for how long, cloud backup off by default.
- **Manager phone:** tables free, a "Needs you" list ordered by urgency, bottom tab bar.

All sample screens use "Sample Café" and labelled sample data. Estimates read "~N" or "about", as in the campus apps.

# DineMate Business — design

Design for the business app (`apps/business`, Phases 8–10). Designed in Figma first; build only after the owner approves it. Figma file: page "DineMate Business v2 — for review" (seven screens including Cameras) (campus redesign is on "Redesign v4 — final for review").

## Look

Same design language as the campus apps: Bricolage Grotesque for headings and big numbers, DM Sans for everything else, JetBrains Mono for clocks and colour codes only. Raised cards and buttons (a solid darker edge under them), occupancy bars, and the small isometric table scene. Sentence-case labels, text 12 px or larger. Professional and calm: cool grey page, white cards, a graphite sidebar, and one accent (cobalt) for the thing to act on.

| Token      | Hex       | Use                                              |
| ---------- | --------- | ------------------------------------------------ |
| Graphite   | `#1B1F27` | Sidebar, headings, seated tables, dark buttons   |
| Deep       | `#0F1217` | Raised edge under graphite cards and buttons     |
| Background | `#F4F5F7` | Page background                                  |
| Card       | `#FFFFFF` | Panels and cards                                 |
| Line       | `#E2E5EA` | Borders and dividers                             |
| Ink        | `#161A21` | Body text                                        |
| Muted      | `#5E6673` | Secondary text                                   |
| Cobalt     | `#2F5BEA` | Active page, main button, live, likely free soon |
| Green      | `#1E8E5A` | Free tables, good numbers                        |
| Amber      | `#B7791F` | Held tables (bag on a seat)                      |
| Red        | `#C23B32` | Needs attention: unstaffed counter, long queue   |

Cobalt is never a status colour, so the table states stay unambiguous. No purple, and no forest green as a brand colour, so the business app is clearly a different product from the campus app. An earlier navy, cream and coral version is archived in Figma.

## Table states

| State            | Look                                     |
| ---------------- | ---------------------------------------- |
| Free             | Green outline on pale green, "4 seats"   |
| Seated           | Graphite, party size and time seated     |
| Likely free soon | Graphite with a cobalt ring, "~5–10 min" |
| Held by a bag    | Amber stripes, time held                 |
| Needs clearing   | Dashed grey outline, time since leaving  |

## Screens

Left navigation on laptop and tablet: Live floor, Customers, Staff, Sales, Reports, Cameras, Privacy & consent, Settings. Venue switcher at the top, server status at the bottom. Every page is reachable in one click.

- **Live floor:** table map with states and timers, tables free now, guests seated, average stay, counter staffing; "Freeing up soon" list and "Needs attention" (clear a table, held tables).
- **Customers:** anonymous visits, average stay, table turns, stay after paying (matched to till orders), visits by hour, stay by table.
- **Staff (owner only):** counter coverage and gaps, items served from the till, serve time, time per work area per worker, how each worker is recognised.
- **Privacy & consent:** staff consent list (face or badge, enrol, view data, remove), what is kept and for how long, cloud backup off by default.
- **Cameras:** live video from one camera at a time with tracking drawn on it: green boxes on customers with time seated, cobalt boxes on staff with role and items served, staff paths, table outlines with their state, the counter area, and the queue. Switches turn each layer on or off; customer faces are blurred by default. Beside it: what the camera sees now, camera health, and a note that video is live only and never saved. Live floor has a Watch live button. Staff are labelled by role (Barista 1), never by real name in sample screens.
- **Manager phone:** tables free, a "Needs you" list ordered by urgency, bottom tab bar.

All sample screens use "Sample Café" and labelled sample data. Estimates read "~N" or "about", as in the campus apps.

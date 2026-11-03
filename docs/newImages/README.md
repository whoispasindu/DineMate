# DineMate image replacement pack

Generated sample assets for manual integration. Application code and existing images have not been changed.

Open `index.html` in your browser to browse all 48 images with filenames and dimensions. Click an image to open its PNG master.

## Contents

- `canteens/`: three fictional canteen cover photos, reusable for thumbnails, cards and detail heroes.
- `food/`: one image per distinct menu item in the sample client and API seed (29 dishes/drinks; vegetable fried rice is shared across shops).
- `shops/`: seven category thumbnails covering all nine sample shops.
- `welcome/`: the welcome illustration.
- `empty-states/`: eight optional spot illustrations with transparent backgrounds.
- `prompts.json`: exact prompts and built-in image_gen generation settings.
- `manifest.json`: validated file inventory with dimensions, transparency, checksums and placement mapping.

All 48 PNGs were checked for readability. The 3 canteen covers are 1536×1024; the other 45 images are 1254×1254. All 8 empty-state PNGs have confirmed transparency. The PNG masters total approximately 101 MB.

These images are generated representations. They are not photos of actual campus facilities, real shop meals, portions or ingredients. Keep the app's sample-image disclosure when using them. Canteen images do not represent current occupancy.

## Where to replace artwork

| App location                                     | Current component/source                                                                                         | Files                                                                           |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Home and canteen list: cards, rows and best spot | `apps/student/src/components/canteen.tsx` → `CanteenArt`                                                         | `canteens/canteen-a.png`, `canteen-b.png`, `canteen-c.png`, keyed by canteen ID |
| Canteen detail: mobile cover and desktop hero    | `apps/student/src/screens/Canteen.tsx` → `CanteenArt`                                                            | Reuse the same three canteen images                                             |
| Welcome screen                                   | `apps/student/src/screens/Welcome.tsx` → `CanteenArt`                                                            | `welcome/welcome-hero.png`                                                      |
| Student menu item: mobile rows and desktop cards | `apps/student/src/screens/Food.tsx` → `ItemArt` → `FoodArt`                                                      | Match the exact item name to the corresponding `food/` file using the manifest  |
| Staff menu editor preview                        | `apps/console/src/screens/Shops.tsx` → `FoodArt`                                                                 | Reuse the same menu item images; no separate staff set needed                   |
| Shop selectors and home/canteen shop lists       | `Food.tsx`, `Home.tsx`, `Canteen.tsx` → `shopArtFor`                                                             | `shops/` category tiles                                                         |
| Empty/error states                               | `apps/student/src/components/common.tsx` → `MessageCard`, `OfflineCard`; `components/canteen.tsx` → `NoBestSpot` | Optional `empty-states/` files                                                  |

The current artwork is inline React SVG, not files named after these PNGs. Dropping PNGs into the project will not replace it automatically; point the appropriate components at the chosen images when integrating manually.

## Shop category mapping

| Shop ID / sample name            | Image                                                                               |
| -------------------------------- | ----------------------------------------------------------------------------------- |
| `s-rice` Rice & Curry Stall      | `shops/shop-rice.png`                                                               |
| `s-friedrice` Fried Rice Counter | `shops/shop-rice.png` (or reuse `food/chicken-fried-rice.png` for more specificity) |
| `s-kottu` Kottu Corner           | `shops/shop-kottu.png`                                                              |
| `s-shorteats` Short Eats Counter | `shops/shop-short-eats.png`                                                         |
| `s-tea` Tea Kiosk                | `shops/shop-tea.png`                                                                |
| `s-noodle` Noodle Bar            | `shops/shop-noodles.png`                                                            |
| `s-bakery` Bakery Corner         | `shops/shop-bakery.png`                                                             |
| `s-smoothie` Smoothie Stand      | `shops/shop-drinks.png` (or `food/mango-smoothie.png`)                              |
| `s-juice` Juice & Snacks         | `shops/shop-drinks.png` (or `food/lime-juice.png`)                                  |

## Category fallback mapping

If keeping the current `FoodArtKind` selection, use these representative images:

| FoodArtKind      | Image                           |
| ---------------- | ------------------------------- |
| `rice_curry`     | `food/chicken-rice-curry.png`   |
| `fried_rice`     | `food/chicken-fried-rice.png`   |
| `milk_rice`      | `food/milk-rice-lunu-miris.png` |
| `string_hoppers` | `food/string-hoppers-curry.png` |
| `dhal`           | `food/dhal-papadam.png`         |
| `kottu`          | `shops/shop-kottu.png`          |
| `short_eats`     | `shops/shop-short-eats.png`     |
| `bakery`         | `shops/shop-bakery.png`         |
| `noodles`        | `shops/shop-noodles.png`        |
| `tea`            | `food/plain-tea.png`            |
| `drink`          | `shops/shop-drinks.png`         |

Prefer exact item mapping for menu cards so vegetarian, chicken, fish and egg options keep distinct images. Never infer ingredients or dietary suitability from the images.

## Empty-state mapping

- `no-menu.png`: menu not added, no menu for selected meal, no scheduled meals.
- `no-results.png`: search/filter found no items.
- `sensor-offline.png`: no reliable seat information / unavailable sensor data.
- `no-shops.png`: no shops listed.
- `no-canteens.png`: no canteens listed.
- `no-alerts.png`: no alerts today.
- `page-not-found.png`: missing page or canteen.
- `offline.png`: offline / request could not load.

These are optional illustrations for existing icon-only states; do not replace live status indicators, safety symbols or warning text with decorative images.

## Manual integration notes

- Food/shop images are square. Current food rows use 52×52, shop tiles 36–52, desktop food cards a 120px image region.
- Canteen covers are landscape and intended for centered cover crops; adjust object-position if your chosen crop hides a useful landmark.
- Use contain framing for food cards when you want the whole plate or glass visible.
- Empty-state PNGs use alpha; place them on the app background without a separate box.
- Sold-out treatment can remain CSS opacity/grayscale; separate sold-out images are unnecessary.
- Keep existing vector navigation icons, leaf/bench brand marks, PWA icons, charts, gauges, status and safety symbols. They remain appropriate and are outside this replacement pack.
- Zone-editor camera backdrops must come from the corresponding real camera; invented layouts are not replacement assets.
- Resize/compress the selected images for production when integrating. This folder holds PNG masters and is not loaded by the application.

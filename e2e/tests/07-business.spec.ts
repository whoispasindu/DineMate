import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BUSINESS, expectAccessible, PASSWORD, SIM_TOKEN } from "./support";

const VENUE = "v-sample-cafe";

interface Layout {
  zones: { zone_id: string; seats: { seat_id: string }[] }[];
}

async function ownerToken(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${API}/auth/login`, { data: { email: "owner@dinemate.test", password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { access_token: string }).access_token;
}

async function postSeats(request: APIRequestContext, layout: Layout, states: Record<string, { state: string; free_soon?: boolean }>) {
  const zones = layout.zones.map((z) => {
    const counts = { free: 0, occupied: 0, held: 0, unknown: 0 };
    for (const seat of z.seats) counts[(states[seat.seat_id]?.state ?? "free") as keyof typeof counts] += 1;
    return { zone_id: z.zone_id, ...counts };
  });
  const seats = layout.zones.flatMap((z) =>
    z.seats.map((seat) => ({
      seat_id: seat.seat_id,
      zone_id: z.zone_id,
      state: states[seat.seat_id]?.state ?? "free",
      for_s: 900,
      free_soon: states[seat.seat_id]?.free_soon ?? false,
    })),
  );
  const response = await request.post(`${API}/devices/sim-cafe/seats`, {
    headers: { Authorization: `Device ${SIM_TOKEN}` },
    data: { captured_at: new Date(Date.now() - 1000).toISOString(), zones, seats },
  });
  expect(response.ok()).toBeTruthy();
}

test("café owner sees tables change live and marks a table cleared", async ({ page, request }) => {
  const token = await ownerToken(request);
  const layout = (await (
    await request.get(`${API}/business/venues/${VENUE}/tables`, { headers: { Authorization: `Bearer ${token}` } })
  ).json()) as Layout;
  await postSeats(request, layout, {
    "T7-1": { state: "occupied" },
    "T7-2": { state: "occupied" },
    "T3-1": { state: "free", free_soon: true },
  });

  await page.goto(BUSINESS);
  await page.getByLabel("Email").fill("owner@dinemate.test");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Live floor", level: 1 })).toBeVisible();

  const map = page.getByRole("list", { name: "Floor map" });
  await expect(map.getByRole("listitem")).toHaveCount(12);
  await expect(map.getByRole("listitem", { name: /^T7: seated, 2 of 4 seats/ })).toBeVisible();
  await expect(page.getByText("T3 needs clearing")).toBeVisible();
  await page.getByRole("button", { name: "Mark cleared T3" }).click();
  await expect(page.getByText("T3 needs clearing")).toHaveCount(0);
  await expect(map.getByRole("listitem", { name: /^T3: free now/ })).toBeVisible();
});

test("business pages have no serious accessibility violations", async ({ page }) => {
  await page.goto(BUSINESS);
  await page.getByLabel("Email").fill("owner@dinemate.test");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Live floor", level: 1 })).toBeVisible();
  for (const name of ["Live floor", "Customers", "Reports", "Cameras", "Settings"]) {
    await page.getByRole("navigation", { name: "Business" }).getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectAccessible(page);
  }
});

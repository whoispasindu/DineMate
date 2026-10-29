import AxeBuilder from "@axe-core/playwright";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://localhost:8001/api/v1";
export const STUDENT = "http://localhost:5183";
export const CONSOLE = "http://localhost:5184";
export const PASSWORD = process.env.DINEMATE_DEMO_PASSWORD ?? "e2e-demo-password";
export const SIM_TOKEN = "dev-simulator-token";

export async function asStudent(page: Page): Promise<void> {
  await page.addInitScript(() => window.localStorage.setItem("dinemate:welcome-seen", "true"));
}

export async function signIn(page: Page, email: string): Promise<void> {
  await page.goto(CONSOLE);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

export async function expectAccessible(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

export async function postReading(request: APIRequestContext, deviceId: string, zoneName: string, occupied: number): Promise<void> {
  const config = await request.get(`${API}/devices/${deviceId}/config`, { headers: { Authorization: `Device ${SIM_TOKEN}` } });
  const zones = ((await config.json()) as { zones: { zone_id: string; name: string; capacity: number }[] }).zones;
  const zone = zones.find((z) => z.name === zoneName);
  if (!zone) throw new Error(`zone ${zoneName} not on ${deviceId}`);
  const response = await request.post(`${API}/devices/${deviceId}/occupancy`, {
    headers: { Authorization: `Device ${SIM_TOKEN}` },
    data: {
      captured_at: new Date().toISOString(),
      readings: [
        {
          zone_id: zone.zone_id,
          estimated_occupied: occupied,
          occupied_low: occupied - 1,
          occupied_high: Math.min(zone.capacity, occupied + 1),
        },
      ],
    },
  });
  expect(response.status()).toBe(200);
}

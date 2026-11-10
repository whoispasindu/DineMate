import { expect, test } from "@playwright/test";
import { CONSOLE, expectAccessible, signIn } from "./support";

test("admin adds a test video on Devices, opens it in Zones and removes it", async ({ page }) => {
  await signIn(page, "admin@dinemate.test");
  await page.goto(`${CONSOLE}/devices`);
  await expect(page.getByRole("heading", { name: "Devices", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open in Zones for sim-a" })).toBeVisible();

  await page.getByLabel("Canteen").selectOption("b");
  await page.getByLabel("Name", { exact: true }).fill("Lunch clip");
  await page.getByLabel("YouTube link").fill("https://youtu.be/dQw4w9WgXcQ");
  await page.getByLabel("Detail").selectOption("high");
  await page.getByRole("button", { name: "Add test video" }).click();
  await expect(page.getByText(/Added\. The camera computer starts it/)).toBeVisible();
  const row = page.getByRole("listitem").filter({ hasText: "Lunch clip" });
  await expect(row.getByText("Test video", { exact: true })).toBeVisible();
  await expect(row.getByText("Starting…")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expectAccessible(page);

  await row.getByRole("link", { name: "Open in Zones for Lunch clip" }).click();
  await expect(page.getByRole("heading", { name: "Zones", level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: /Lunch clip/ })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText(/No picture yet/)).toBeVisible();

  await page.goto(`${CONSOLE}/devices`);
  const again = page.getByRole("listitem").filter({ hasText: "Lunch clip" });
  await again.getByRole("button", { name: "Remove Lunch clip" }).click();
  await again.getByRole("button", { name: "Remove Lunch clip" }).click();
  await expect(page.getByText("Lunch clip")).toHaveCount(0);
});

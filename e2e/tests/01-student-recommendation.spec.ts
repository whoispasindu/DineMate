import { expect, test } from "@playwright/test";
import { asStudent, expectAccessible, STUDENT } from "./support";

test.beforeEach(async ({ page }) => asStudent(page));

test("home → canteen comparison → recommendation", async ({ page }) => {
  await page.goto(STUDENT);
  const best = page.getByRole("region", { name: "Best spot now" });
  await expect(best.getByRole("heading", { name: "Canteen B" })).toBeVisible();
  await expect(page.getByText(/seats free/).first()).toBeVisible();

  await page.getByRole("navigation").getByRole("link", { name: "Canteens", exact: true }).first().click();
  await expect(page).toHaveURL(/\/canteens\/b$/);
  await expect(page.getByRole("heading", { name: "Canteen B", level: 1 })).toBeVisible();

  await page.goto(`${STUDENT}/canteens/c`);
  const alternative = page.getByRole("link", { name: /Less crowded nearby: Canteen B/ });
  await expect(alternative).toBeVisible();
  await expect(alternative).toContainText("min walk");
  await alternative.click();
  await expect(page).toHaveURL(/\/canteens\/b$/);
  await expect(page.getByRole("link", { name: /Less crowded nearby/ })).toHaveCount(0);
  await expect(page.getByText("Experimental forecast").first()).toBeVisible();
});

test("student pages have no serious accessibility violations", async ({ page }) => {
  for (const path of ["/", "/canteens", "/canteens/a", "/food", "/meals", "/alerts"]) {
    await page.goto(`${STUDENT}${path}`);
    await expect(page.locator("#main")).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectAccessible(page);
  }
});

test("offline shows no seat numbers", async ({ page, context }) => {
  await page.goto(STUDENT);
  await expect(page.getByText(/seats free/).first()).toBeVisible();
  await context.setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
  await expect(page.getByText(/offline/i).first()).toBeVisible();
  await expect(page.getByText(/seats free/)).toHaveCount(0);
  await context.setOffline(false);
});

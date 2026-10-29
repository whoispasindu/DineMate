import { expect, test } from "@playwright/test";
import { CONSOLE, postReading, signIn } from "./support";

test("zone fills up → Crowded alert → admin acknowledges", async ({ page, request }) => {
  await signIn(page, "admin@dinemate.test");
  await page.goto(`${CONSOLE}/config`);
  const dwell = page.getByLabel("Dwell for Main hall");
  await dwell.fill("0");
  const row = page.getByRole("row").filter({ has: dwell });
  await row.getByRole("button", { name: "Save" }).click();
  await expect(row.getByRole("button", { name: "Save" })).toBeDisabled();

  await postReading(request, "sim-c", "Main hall", 46);
  await page.goto(CONSOLE);
  const alert = page.getByRole("listitem").filter({ hasText: "Canteen C — Main hall" }).first();
  await expect(alert.getByRole("button", { name: "Acknowledge" })).toBeVisible({ timeout: 20_000 });
  await alert.getByRole("button", { name: "Acknowledge" }).click();
  await expect(alert).toContainText("Acknowledged by Campus administrator");
});

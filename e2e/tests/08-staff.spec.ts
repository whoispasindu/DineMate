import { expect, test, type Page } from "@playwright/test";
import { BUSINESS, expectAccessible, PASSWORD } from "./support";

const TILL = [
  "order_id,time,cashier,item,qty,unit_price",
  "E2E-1,2026-11-20 12:05,C1,Flat white,3,700",
  "E2E-2,2026-11-20 12:12,C1,Flat white,2,700",
  "E2E-3,2026-11-20 12:20,ZZ,Tea,1,300",
].join("\n");

async function signInBusiness(page: Page, email: string): Promise<void> {
  await page.goto(BUSINESS);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Live floor", level: 1 })).toBeVisible();
}

function nav(page: Page) {
  return page.getByRole("navigation", { name: "Business" });
}

test("owner imports a till file, sees items per worker, and the view is audited", async ({ page }) => {
  await signInBusiness(page, "owner@dinemate.test");

  await nav(page).getByRole("link", { name: "Sales" }).click();
  await expect(page.getByRole("heading", { name: "Sales", level: 1 })).toBeVisible();
  await page.getByLabel("Choose CSV file").setInputFiles({ name: "till.csv", mimeType: "text/csv", buffer: Buffer.from(TILL) });
  await page.getByRole("button", { name: "Check file" }).click();
  await expect(page.getByText(/Checked, nothing saved yet\. 3 rows · 3 orders · 3 new/)).toBeVisible();
  await expect(page.getByText(/Not on the staff list: ZZ/)).toBeVisible();
  await page.getByRole("button", { name: "Import 3 new orders" }).click();
  await expect(page.getByText(/^Imported\./)).toBeVisible();
  await expect(page.getByText(/Flat white 5/).first()).toBeVisible();

  await nav(page).getByRole("link", { name: "Staff" }).click();
  await expect(page.getByRole("heading", { name: "Staff", level: 1 })).toBeVisible();
  const items = page.locator("section").filter({ has: page.getByRole("heading", { name: "Items served" }) });
  await expect(items.getByText(/Flat white 5/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Print sheet for Cashier 1" })).toBeVisible();

  await nav(page).getByRole("link", { name: "Privacy & consent" }).click();
  await expect(page.getByRole("heading", { name: "Privacy & consent", level: 1 })).toBeVisible();
  await expect(page.getByText("opened the staff report").first()).toBeVisible();
});

test("a venue manager sees sales but not the staff report", async ({ page }) => {
  await signInBusiness(page, "manager@dinemate.test");
  await expect(nav(page).getByRole("link", { name: "Sales" })).toBeVisible();
  await expect(nav(page).getByRole("link", { name: "Staff" })).toHaveCount(0);
  await expect(nav(page).getByRole("link", { name: "Privacy & consent" })).toHaveCount(0);
  await page.goto(`${BUSINESS}/staff`);
  await expect(page.getByText("The staff report is for the owner only.", { exact: false })).toBeVisible();
});

test("staff pages have no serious accessibility violations", async ({ page }) => {
  await signInBusiness(page, "owner@dinemate.test");
  for (const name of ["Staff", "Sales", "Privacy & consent"]) {
    await nav(page).getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectAccessible(page);
  }
});

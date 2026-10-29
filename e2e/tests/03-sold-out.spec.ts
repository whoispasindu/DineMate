import { expect, test } from "@playwright/test";
import { asStudent, CONSOLE, signIn, STUDENT } from "./support";

test("shop manager marks an item sold out → student food page shows it", async ({ page, browser }) => {
  await signIn(page, "rice.stall@dinemate.test");
  await expect(page).toHaveURL(`${CONSOLE}/shops`);
  const row = page.getByRole("row").filter({ hasText: "Vegetable rice & curry" });
  await row.getByRole("button", { name: "Available" }).click();
  await expect(row.getByRole("button", { name: "Sold out" })).toHaveAttribute("aria-pressed", "true");

  const student = await browser.newPage();
  await asStudent(student);
  await student.goto(`${STUDENT}/food?canteen=a&shop=s-rice`);
  const item = student.getByRole("listitem").filter({ hasText: "Vegetable rice & curry" }).first();
  await expect(item).toContainText("Sold out");

  await row.getByRole("button", { name: "Sold out" }).click();
  await expect(row.getByRole("button", { name: "Available" })).toBeVisible();
  await student.close();
});

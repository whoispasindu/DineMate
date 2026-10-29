import { expect, test } from "@playwright/test";
import { asStudent, CONSOLE, signIn, STUDENT } from "./support";

test("simulated safety alert → labelled everywhere → officer acknowledges and resolves", async ({ page, browser }) => {
  await signIn(page, "safety@dinemate.test");
  await expect(page).toHaveURL(`${CONSOLE}/safety`);
  await page.getByLabel("Location").selectOption({ label: "Canteen A" });
  await page.getByLabel("Note for the log").fill("E2E demo run");
  await page.getByRole("button", { name: "Trigger simulation" }).click();

  await expect(page.getByText("Fire alarm (simulated)", { exact: true })).toBeVisible();
  await expect(page.getByText("SIMULATION — NOT A REAL EMERGENCY").nth(1)).toBeVisible();

  const student = await browser.newPage();
  await asStudent(student);
  await student.goto(STUDENT);
  await expect(student.getByText("SIMULATION — NOT A REAL EMERGENCY").first()).toBeVisible({ timeout: 15_000 });
  await expect(student.getByText("Fire alarm (simulated) · Canteen A")).toBeVisible();

  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await expect(page.getByText(/Acknowledged by Safety officer/)).toBeVisible();
  await page.getByLabel("Resolution note (required)").fill("E2E drill finished");
  await page.getByRole("button", { name: "Resolve" }).click();
  await expect(page.getByText("No open safety events.")).toBeVisible();
  await expect(page.getByText(/resolved by Safety officer/)).toBeVisible();
  await expect(page.getByText("“E2E drill finished”")).toBeVisible();

  await expect(student.getByText("Fire alarm (simulated) · Canteen A")).toHaveCount(0, { timeout: 15_000 });
  await student.close();
});

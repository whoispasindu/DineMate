import { expect, test } from "@playwright/test";
import { API, asStudent, STUDENT } from "./support";

function seconds(text: string): number {
  const parts = text.trim().split(":").map(Number);
  return parts.reduce((total, part) => total * 60 + part, 0);
}

test("lunch countdown follows the server clock even when the device clock is wrong", async ({ page, request }) => {
  await asStudent(page);
  await page.clock.install({ time: new Date(Date.now() + 10 * 60_000) });
  await page.clock.resume();

  const status = await (await request.get(`${API}/meal-status`)).json();
  expect(status.current?.period).toBe("lunch");
  const expected = (Date.parse(status.current.ends) - Date.parse(status.server_time)) / 1000;

  await page.goto(`${STUDENT}/meals`);
  const card = page.getByRole("region", { name: "Meal countdown" });
  await expect(card).toContainText("until lunch ends");
  const first = seconds((await card.textContent())?.match(/\d{2}:\d{2}:\d{2}/)?.[0] ?? "");
  expect(Math.abs(first - expected)).toBeLessThan(15);

  await page.reload();
  const reloaded = page.getByRole("region", { name: "Meal countdown" });
  await expect(reloaded).toContainText("until lunch ends");
  const afterReload = seconds((await reloaded.textContent())?.match(/\d{2}:\d{2}:\d{2}/)?.[0] ?? "");
  expect(afterReload).toBeLessThanOrEqual(first);
  expect(first - afterReload).toBeLessThan(15);
});

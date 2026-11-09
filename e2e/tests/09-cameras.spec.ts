import { expect, test, type Page } from "@playwright/test";
import { BUSINESS, expectAccessible, PASSWORD } from "./support";

const ADDRESS = "rtsp://admin:camera-secret@192.168.1.77:554/stream1";

async function signInOwner(page: Page): Promise<void> {
  await page.goto(BUSINESS);
  await page.getByLabel("Email").fill("owner@dinemate.test");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Live floor", level: 1 })).toBeVisible();
  await page.getByRole("navigation", { name: "Business" }).getByRole("link", { name: "Cameras" }).click();
  await expect(page.getByRole("heading", { name: "Cameras", level: 1 })).toBeVisible();
}

test("owner adds a camera, draws seats on it and removes it", async ({ page }) => {
  await signInOwner(page);
  await page.getByLabel("Name", { exact: true }).fill("Counter camera");
  await page.getByLabel("Camera address").fill(ADDRESS);
  await page.getByRole("button", { name: "Add camera" }).click();
  await expect(page.getByText(/Added\. The camera computer picks it up/)).toBeVisible();
  await expect(page.getByText(/rtsp:\/\/192\.168\.1\.77:554\/…/)).toBeVisible();
  await expect(page.getByText("Waiting for the camera computer")).toBeVisible();
  await expect(page.getByText("camera-secret")).toHaveCount(0);
  await page.waitForLoadState("networkidle");
  await expectAccessible(page);

  await page.getByRole("link", { name: "Set up zones for Counter camera" }).click();
  await expect(page.getByRole("heading", { name: "Counter camera", level: 1 })).toBeVisible();
  await expect(page.getByText(/No picture yet/)).toBeVisible();
  await page.getByRole("button", { name: "Seating", exact: true }).click();
  await page.getByRole("button", { name: "Place seats" }).click();
  const canvas = page.getByRole("application", { name: /Zone layout canvas/ });
  const box = await canvas.boundingBox();
  if (!box) throw new Error("canvas not visible");
  await page.mouse.click(box.x + box.width * 0.45, box.y + box.height * 0.45);
  await page.mouse.click(box.x + box.width * 0.55, box.y + box.height * 0.55);
  await expect(page.getByText(/^2 seats/)).toBeVisible();
  await page.getByRole("button", { name: "Done placing seats" }).click();
  await page.waitForLoadState("networkidle");
  await expectAccessible(page);
  await page.getByRole("button", { name: "Save layout" }).click();
  await expect(page.getByText(/Saved as version 1/)).toBeVisible();

  await page.getByRole("link", { name: "Back to cameras" }).click();
  await page.getByRole("button", { name: "Remove Counter camera" }).click();
  await page.getByRole("button", { name: "Remove Counter camera" }).click();
  await expect(page.getByText(/rtsp:\/\/192\.168\.1\.77/)).toHaveCount(0);
});

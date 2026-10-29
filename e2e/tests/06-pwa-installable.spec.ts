import { expect, test } from "@playwright/test";

const PREVIEW = "http://localhost:4183";

interface Manifest {
  name?: string;
  short_name?: string;
  start_url?: string;
  display?: string;
  icons?: { src: string; sizes: string; purpose?: string }[];
}

test("production build is installable: manifest and an active service worker", async ({ page, request }) => {
  await page.addInitScript(() => window.localStorage.setItem("dinemate:welcome-seen", "true"));
  await page.goto(PREVIEW);
  const href = await page.locator('link[rel="manifest"]').getAttribute("href");
  expect(href).toBeTruthy();
  const manifest = (await (await request.get(new URL(href ?? "", PREVIEW).toString())).json()) as Manifest;
  expect(manifest.name).toBe("DineMate");
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBeTruthy();
  const sizes = (manifest.icons ?? []).map((i) => i.sizes);
  expect(sizes).toEqual(expect.arrayContaining(["192x192", "512x512"]));
  expect((manifest.icons ?? []).some((i) => i.purpose === "maskable")).toBe(true);

  const scope = await page.evaluate(async () => (await navigator.serviceWorker.ready).scope);
  expect(scope).toBe(`${PREVIEW}/`);
  await page.reload();
  expect(await page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);
});

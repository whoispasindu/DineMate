import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { API, asStudent, BUSINESS, CONSOLE, PASSWORD, signIn, SIM_TOKEN, STUDENT } from "../tests/support";

const OUT = fileURLToPath(new URL("../../docs/screenshots/", import.meta.url));
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true };
const LAPTOP = { viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1.5 };
const WIDE = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.25 };

async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
}

async function studentPage(browser: Browser, size: typeof PHONE | typeof LAPTOP): Promise<Page> {
  const context = await browser.newContext(size);
  const page = await context.newPage();
  await asStudent(page);
  return page;
}

async function shot(page: Page, name: string, fullPage = false): Promise<void> {
  await settle(page);
  await page.screenshot({ path: `${OUT}${name}.png`, fullPage });
}

test.describe.configure({ mode: "serial" });

test("welcome screen on a phone", async ({ browser }) => {
  const context = await browser.newContext(PHONE);
  const page = await context.newPage();
  await page.goto(`${STUDENT}/welcome`);
  await expect(page.getByRole("button", { name: /Find a seat/ })).toBeVisible();
  await shot(page, "student-welcome-phone");
  await context.close();
});

test("student app on a phone", async ({ browser }) => {
  const page = await studentPage(browser, PHONE);
  await page.goto(STUDENT);
  await expect(page.getByRole("region", { name: "Best spot now" })).toBeVisible();
  await shot(page, "student-home-phone");

  await page.goto(`${STUDENT}/canteens/c`);
  await expect(page.getByRole("link", { name: /Less crowded nearby/ })).toBeVisible();
  await shot(page, "student-canteen-phone");

  await page.goto(`${STUDENT}/food?canteen=a&shop=s-rice`);
  await expect(page.getByText("Vegetable rice & curry")).toBeVisible();
  await shot(page, "student-food-phone");

  await page.goto(`${STUDENT}/meals`);
  await expect(page.getByRole("region", { name: "Meal countdown" })).toBeVisible();
  await shot(page, "student-meals-phone");
  await page.context().close();
});

test("student app on a laptop", async ({ browser }) => {
  const page = await studentPage(browser, LAPTOP);
  await page.goto(STUDENT);
  await expect(page.getByRole("region", { name: "Best spot now" })).toBeVisible();
  await shot(page, "student-home-laptop");

  await page.goto(`${STUDENT}/canteens/b`);
  await expect(page.getByText("Experimental forecast").first()).toBeVisible();
  await shot(page, "student-canteen-laptop", true);

  await page.goto(`${STUDENT}/food?canteen=b&shop=s-smoothie`);
  await expect(page.getByText("Mango smoothie")).toBeVisible();
  await shot(page, "student-food-laptop");
  await page.context().close();
});

async function postSampleSeats(request: APIRequestContext): Promise<void> {
  const headers = { Authorization: `Device ${SIM_TOKEN}` };
  const config = (await (await request.get(`${API}/devices/sim-a/config`, { headers })).json()) as {
    zones: { zone_id: string; capacity: number }[];
  };
  const zones = config.zones.map((z, i) => {
    const held = 4;
    const unknown = i === 0 ? 2 : 0;
    const occupied = Math.round(z.capacity * (i === 0 ? 0.75 : 0.62));
    return {
      zone_id: z.zone_id,
      free: z.capacity - occupied - held - unknown,
      occupied,
      held,
      unknown,
      free_soon: 2,
      standing: i === 0 ? 5 : 1,
      crowded: i === 0,
    };
  });
  const response = await request.post(`${API}/devices/sim-a/seats`, {
    headers,
    data: { captured_at: new Date(Date.now() - 1000).toISOString(), zones, seats: [] },
  });
  expect(response.ok()).toBeTruthy();
}

test("staff console", async ({ browser, request }) => {
  await postSampleSeats(request);
  for (const [email, path, name, ready] of [
    ["admin@dinemate.test", "/", "console-overview", "Live occupancy by zone"],
    ["rice.stall@dinemate.test", "/shops", "console-shops", "Rice & Curry Stall"],
    ["canteen.a@dinemate.test", "/occupancy", "console-occupancy", "Estimated seats in use"],
    ["canteen.a@dinemate.test", "/seats", "console-seats", "By zone"],
  ] as const) {
    const context = await browser.newContext(WIDE);
    const page = await context.newPage();
    await signIn(page, email);
    await page.goto(`${CONSOLE}${path}`);
    await expect(page.getByText(ready).first()).toBeVisible();
    await shot(page, name);
    await context.close();
  }
});

test("zone editor with a selected zone", async ({ browser }) => {
  const context = await browser.newContext(WIDE);
  const page = await context.newPage();
  await signIn(page, "canteen.a@dinemate.test");
  await page.goto(`${CONSOLE}/zones`);
  await page.getByRole("button", { name: /^sim-a/ }).click();
  const label = page.getByText("Terrace · 40");
  await expect(label).toBeVisible();
  const box = await label.boundingBox();
  if (box) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page.getByRole("button", { name: /Corner 1/ })).toBeVisible();
  await shot(page, "console-zones");
  await context.close();
});

test("labelled safety simulation", async ({ browser }) => {
  const context = await browser.newContext(WIDE);
  const officer = await context.newPage();
  await signIn(officer, "safety@dinemate.test");
  await officer.getByLabel("Location").selectOption({ label: "Canteen A" });
  await officer.getByLabel("Note for the log").fill("Judging demo");
  await officer.getByRole("button", { name: "Trigger simulation" }).click();
  await expect(officer.getByText("Fire alarm (simulated)", { exact: true })).toBeVisible();
  await shot(officer, "console-safety");

  const student = await studentPage(browser, PHONE);
  await student.goto(STUDENT);
  await expect(student.getByText("SIMULATION — NOT A REAL EMERGENCY").first()).toBeVisible();
  await shot(student, "student-safety-phone");

  await officer.getByLabel("Resolution note (required)").fill("Drill finished");
  await officer.getByRole("button", { name: "Resolve" }).click();
  await expect(officer.getByText("No open safety events.")).toBeVisible();
  await student.context().close();
  await context.close();
});

async function businessPage(browser: Browser, size: typeof PHONE | typeof WIDE): Promise<Page> {
  const context = await browser.newContext(size);
  const page = await context.newPage();
  await page.goto(BUSINESS);
  await page.getByLabel("Email").fill("owner@dinemate.test");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Live floor", level: 1 })).toBeVisible();
  return page;
}

test("DineMate Business dashboard", async ({ browser }) => {
  const page = await businessPage(browser, WIDE);
  await expect(page.getByRole("list", { name: "Floor map" }).getByRole("listitem")).toHaveCount(12);
  await shot(page, "business-floor");
  for (const [name, file] of [
    ["Customers", "business-customers"],
    ["Reports", "business-reports"],
  ] as const) {
    await page.getByRole("navigation", { name: "Business" }).getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
    await shot(page, file);
  }
  await page.context().close();

  const phone = await businessPage(browser, PHONE);
  await shot(phone, "business-floor-phone");
  await phone.context().close();
});

import type { Locator, Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

export const shots = resolve("..", "docs", "screenshots", "final_release");

/** The boot splash plays once per browser session; journeys start after it. */
export async function skipSplash(page: Page) {
  await page.addInitScript(() =>
    sessionStorage.setItem("boussla.boot.v1", "1"),
  );
}

/** Release screenshots only when BOUSSLA_E2E_SCREENSHOTS=1 (synthetic data only). */
export async function capture(
  page: Page,
  name: string,
  target?: Locator,
  fullPage = false,
  settleMs = 450,
) {
  if (process.env.BOUSSLA_E2E_SCREENSHOTS !== "1") return;
  mkdirSync(shots, { recursive: true });
  await page.waitForTimeout(settleMs); // let one-time entrances settle
  if (target) {
    await target.scrollIntoViewIfNeeded();
    await target.screenshot({ path: resolve(shots, name) });
  } else {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: resolve(shots, name), fullPage });
  }
}

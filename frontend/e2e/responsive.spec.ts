import { expect, test } from "@playwright/test";
import { skipSplash } from "./support";

for (const width of [320, 390, 768]) {
  test(`agent and company pages fit a ${width}px viewport`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 850 });
    await skipSplash(page);
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Portefeuille des entreprises" }),
    ).toBeVisible();

    for (const tab of ["Dossiers", "Réseau", "Historique", "Notifications"]) {
      await page
        .getByRole("button", { name: tab, exact: true })
        .first()
        .click();
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
    }
    await page.getByRole("button", { name: "Entreprise", exact: true }).click();
    for (const tab of [
      "Mes dossiers",
      "Actions requises",
      "Documents",
      "Messages",
    ]) {
      const button = page
        .getByRole("button", { name: tab, exact: true })
        .first();
      await button.click();
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
    }
  });
}

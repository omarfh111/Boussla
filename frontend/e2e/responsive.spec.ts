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
      const loaded =
        tab === "Réseau" || tab === "Notifications"
          ? page.waitForResponse((response) =>
              response
                .url()
                .includes(
                  tab === "Réseau" ? "/network/case/" : "/notifications",
                ),
            )
          : null;
      await page
        .getByRole("button", { name: tab, exact: true })
        .first()
        .click();
      if (loaded) await loaded;
      await expect(page.locator(".skeletons")).toHaveCount(0);
      if (tab === "Notifications") {
        await expect(
          page.getByText("Chargement des mises à jour…"),
        ).toHaveCount(0);
        await expect(
          page.getByRole("heading", { name: "Mises à jour internes" }),
        ).toBeVisible();
      }
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
      const loaded =
        tab === "Messages"
          ? page.waitForResponse((response) =>
              response.url().includes("/notifications"),
            )
          : null;
      await button.click();
      if (loaded) await loaded;
      if (tab === "Messages") {
        await expect(
          page.getByText("Chargement des mises à jour…"),
        ).toHaveCount(0);
        await expect(
          page.getByRole("heading", { name: "Mises à jour internes" }),
        ).toBeVisible();
      }
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
    }
  });
}

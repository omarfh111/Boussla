import { test, expect } from "@playwright/test";

test("the first-load introduction fades when skipped and stays dismissed", async ({
  page,
}) => {
  await page.goto("/");
  const splash = page.getByRole("status", { name: "Chargement de BOUSSLA" });
  await expect(splash).toBeVisible();
  await splash.getByRole("button", { name: "Passer l’introduction" }).click();
  await expect(splash).toHaveClass(/leaving/);
  await expect(splash).toHaveCount(0, { timeout: 1500 });
  await page.reload();
  await expect(splash).toHaveCount(0);
});

test("reduced motion opens the application without an introduction", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("status", { name: "Chargement de BOUSSLA" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toBeVisible();
});

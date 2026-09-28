import { test, expect } from "@playwright/test";
import { skipSplash } from "./support";

test.beforeEach(async ({ page }) => skipSplash(page));

test("portfolio search, filters, sorting, disclosure and keyboard opening", async ({
  page,
}) => {
  await page.goto("/");
  const rows = page.locator(".portfolio-card-item");
  await expect(rows).toHaveCount(13);
  await expect(rows.first().locator(".portfolio-triage")).toHaveText("82");

  await page
    .getByRole("searchbox", { name: "Rechercher une entreprise" })
    .fill("Dune");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("Fournitures Dune");
  await page
    .getByRole("button", { name: "Réinitialiser", exact: true })
    .click();
  await expect(rows).toHaveCount(13);

  await page.getByRole("button", { name: "Preuves incomplètes" }).click();
  expect(await rows.count()).toBeGreaterThan(0);
  await expect(
    page.getByRole("button", { name: "Preuves incomplètes" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Réinitialiser", exact: true })
    .click();

  await page.getByLabel("Trier par").selectOption("name");
  await expect(rows.first()).toContainText("Bâtisseur Démo");
  await page.getByLabel("Trier par").selectOption("triage");
  await expect(rows.first()).toContainText("Travaux Opale");

  await expect(
    rows.first().locator(".portfolio-row-reasons summary"),
  ).toContainText("Constat de revue présent");
  await rows.first().locator(".portfolio-row-reasons summary").click();
  await expect(
    rows
      .first()
      .locator(".portfolio-row-reasons li")
      .getByText("Divergences de transactions à examiner"),
  ).toBeVisible();
  await rows
    .first()
    .getByRole("button", { name: "Ouvrir SYNTHÉTIQUE — Travaux Opale" })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "SYN-OP-012-CASE", level: 1 }),
  ).toBeVisible();
});

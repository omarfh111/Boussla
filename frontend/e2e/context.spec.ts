import { test, expect, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

// Context consistency on the real service: clarification only, never priority.
// BOUSSLA_E2E_LIVE=1 when the server runs with a configured model (interpretation LIVE).
const live = process.env.BOUSSLA_E2E_LIVE === "1";
const shots = resolve("..", "docs", "screenshots", "react_ui");
const purpose =
  "Construction d'un dépôt logistique prévue sur environ dix-huit mois";

async function officerPriority(page: Page) {
  await page.getByRole("button", { name: "Agent", exact: true }).click();
  await page.getByRole("button", { name: "Dossier", exact: true }).click();
  const ring = page.locator(".priority-ring strong");
  await expect(ring).toHaveText(/\d+/);
  return ring.textContent();
}

async function declare(page: Page, horizon: string, stage: string) {
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await page.getByRole("button", { name: "Contexte" }).click();
  await page.getByLabel("Horizon du projet (déclaré)").selectOption(horizon);
  await page.getByPlaceholder("Décrivez l’affectation prévue…").fill(purpose);
  await page.getByPlaceholder("Ex. projet P1").fill("Maître d’ouvrage privé");
  await page.getByPlaceholder("Ex. gros œuvre").fill(stage);
  await page.getByLabel("Début prévu").fill("2027-01-01");
  await page.getByLabel("Fin prévue").fill("2028-06-30");
  await page
    .getByRole("button", { name: "Enregistrer la déclaration" })
    .click();
  await expect(
    page.getByText("Contexte déclaré et nouvelle version créée."),
  ).toBeVisible();
}

test("context mismatch asks for clarification, correction becomes consistent, priority unchanged", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "File de revue" }),
  ).toBeVisible();
  const before = await officerPriority(page);

  await declare(page, "SHORT_HORIZON", "");
  const tiles = page.locator(".context-grid .metric");
  await expect(tiles.nth(0)).toContainText("Horizon court");
  await expect(tiles.nth(1)).toContainText(
    live ? "Horizon plus long" : "Non disponible",
  );
  await expect(tiles.nth(2)).toContainText("546 jours · Horizon plus long");
  await expect(tiles.nth(3)).toContainText("Clarification nécessaire");
  await expect(
    page.getByText(
      "La période déclarée diffère de celle calculée depuis les dates.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText(/n’affecte pas automatiquement la priorité de revue/),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/risque|fraude/i);
  if (process.env.BOUSSLA_E2E_SCREENSHOTS === "1") {
    mkdirSync(shots, { recursive: true });
    await page
      .locator(".panel", { has: page.locator(".context-grid") })
      .evaluate((el) => el.scrollIntoView({ block: "start" }));
    await page.screenshot({
      path: resolve(shots, "03_context_consistency.png"),
    });
  }
  expect(await officerPriority(page)).toBe(before);

  await declare(page, "LONGER_HORIZON", "Gros œuvre");
  await expect(tiles.nth(0)).toContainText("Horizon plus long");
  await expect(tiles.nth(3)).toContainText("Cohérent");
  // Both declarations remain listed: the correction supersedes, it does not overwrite.
  await expect(
    page.locator(".record").filter({ hasText: purpose }),
  ).toHaveCount(2);
  expect(await officerPriority(page)).toBe(before);
});

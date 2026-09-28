import { test, expect, type Page } from "@playwright/test";
import { capture, skipSplash } from "./support";

// JOURNEY 2 — context inconsistency -> automatic questionnaire -> company response ->
// investigator refresh. Clarification only: the review index never moves.
// BOUSSLA_E2E_LIVE=1 when the server runs with a configured model (interpretation LIVE).
const live = process.env.BOUSSLA_E2E_LIVE === "1";
const purpose =
  "Construction d'un dépôt logistique prévue sur environ dix-huit mois";

test.beforeEach(async ({ page }) => skipSplash(page));

async function officerPriority(page: Page) {
  await page.getByRole("button", { name: "Agent", exact: true }).click();
  await page.getByRole("button", { name: "Dossiers", exact: true }).click();
  const ring = page.locator(".priority-ring strong");
  await expect(ring).toHaveText(/\d+/);
  return ring.textContent();
}

async function declare(page: Page, horizon: string, stage: string) {
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await page.getByRole("button", { name: "Messages" }).click();
  await page.locator("summary").filter({ hasText: "Contexte déclaré" }).click();
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

test("context mismatch -> automatic questionnaire -> response -> investigator refresh", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toBeVisible();
  const before = await officerPriority(page);

  await declare(page, "SHORT_HORIZON", "Gros œuvre");
  const tiles = page.locator(".context-grid .metric");
  await expect(tiles.nth(0)).toContainText("Horizon court");
  await expect(tiles.nth(1)).toContainText(
    live ? "Horizon plus long" : "Non disponible",
  );
  await expect(tiles.nth(2)).toContainText("546 jours · Horizon plus long");
  await expect(tiles.nth(3)).toContainText("Clarification nécessaire");
  await expect(page.locator("body")).not.toContainText(/risque|fraude/i);

  // The questionnaire arrived without any officer action.
  await page.getByRole("button", { name: "Actions requises" }).click();
  const card = page
    .locator(".stack > div")
    .filter({ hasText: "Demande automatique BOUSSLA" })
    .first();
  await expect(card.getByText("Demande automatique BOUSSLA")).toBeVisible();
  await expect(
    card.getByText(
      "Précisions demandées automatiquement à partir des informations disponibles.",
    ),
  ).toBeVisible();
  await expect(
    card.getByText(/Cible de réponse de démonstration/),
  ).toBeVisible();
  await expect(card.locator(".question-list li")).toHaveCount(3);
  await expect(card.locator(".question-list li").first()).toContainText(
    "courte (90 jours ou moins) ou plus longue",
  );
  await capture(page, "05_context_auto_questionnaire.png", card);

  // Company answers the fixed-choice confirmation (the enum value is sent).
  await card.getByRole("button", { name: "Répondre à la demande" }).click();
  await page
    .locator(".response-form select:has(option[value=''])")
    .first()
    .selectOption("LONGER_HORIZON");
  await page.getByRole("button", { name: "Transmettre la réponse" }).click();
  await expect(
    page.getByText("Réponse transmise à la revue de l’agent."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Messages" }).click();
  await page.locator("summary").filter({ hasText: "Contexte déclaré" }).click();
  await expect(tiles.nth(0)).toContainText("Horizon plus long");
  await expect(tiles.nth(3)).toContainText("Cohérent");

  // Officer: same review index; the assisted analysis reflects the new version.
  expect(await officerPriority(page)).toBe(before);
  await page
    .locator("summary")
    .filter({ hasText: "Enquête détaillée et simulations" })
    .click();
  const brief = page.locator(".investigator-panel");
  await expect(
    brief.getByText("Changements depuis la version précédente"),
  ).toBeVisible();
  await expect(brief).toContainText("Réponse de l'entreprise reçue");
  await expect(
    brief.getByText(
      "L'analyse assistée ne modifie pas l'indice de revue ni les faits du dossier.",
    ),
  ).toBeVisible();
});

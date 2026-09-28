import { test, expect } from "@playwright/test";
import { resolve } from "node:path";
import { capture, skipSplash } from "./support";

// JOURNEY 3 — brick case: automatic clarification -> evidence upload -> officer
// accepts -> provisional review index 20 -> 0 -> previous revision preserved.
const pdf = resolve(
  "..",
  "docs",
  "build_lock",
  "fixtures",
  "documents",
  "06_second_project_allocation.pdf",
);
const officerHeaders = { "X-Boussla-Demo-Role": "OFFICER" };

test.beforeEach(async ({ page }) => skipSplash(page));

test("brick case: automatic request, provisional evidence, human acceptance", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toBeVisible();
  const brick = page
    .locator(".portfolio-card-item")
    .filter({ hasText: "CASE-BRICKS-001" });
  await expect(brick.locator(".portfolio-index")).toHaveText("40");

  // Company declares context: the service publishes the neutral request itself.
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Votre dossier, en un regard" }),
  ).toBeVisible();
  await expect(
    page.getByText("Priorité de revue", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Messages" }).click();
  await page.locator("summary").filter({ hasText: "Contexte déclaré" }).click();
  await page
    .getByPlaceholder("Décrivez l’affectation prévue…")
    .fill("Matériaux destinés au lot P1 et au lot P2.");
  await page.getByPlaceholder("Ex. projet P1").fill("Projet de maçonnerie");
  await page
    .getByRole("button", { name: "Enregistrer la déclaration" })
    .click();
  await expect(
    page.getByText("Contexte déclaré et nouvelle version créée."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Agent", exact: true }).click();
  await page.getByRole("button", { name: "Dossiers", exact: true }).click();
  await expect(page.locator(".priority-ring strong")).toHaveText("40");
  await expect(page.getByText("Impact si résolu")).toBeVisible();
  await expect(page.locator(".impact-list").getByText("40 → 0")).toBeVisible();
  await expect(page.locator(".request-mini")).toContainText("REQ-AUTO-");
  await expect(
    page
      .locator(".request-mini")
      .getByText("Demande automatique BOUSSLA")
      .first(),
  ).toBeVisible();
  await page
    .getByText("Enquête détaillée et simulations", { exact: true })
    .click();
  const scenarios = page.locator(".scenario-panel");
  await expect(
    scenarios.getByText("Réaffectation hypothétique P1=1000 / P2=1000"),
  ).toBeVisible();
  await expect(
    scenarios.getByText(
      "Simulation hypothétique — aucun changement du dossier.",
    ),
  ).toBeVisible();
  await capture(page, "07_scenarios.png", scenarios);
  await page.getByRole("button", { name: "Avancé" }).click();
  await page.getByText("Références", { exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Passages de référence candidats à examiner",
    }),
  ).toBeVisible();
  await capture(page, "08_rag_references.png");

  // Company responds to the automatic request with a document and a reallocation.
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await page.getByRole("button", { name: "Actions requises" }).click();
  await page
    .getByRole("button", { name: "Répondre à la demande" })
    .first()
    .click();
  await page.locator(".attachment-row input").setInputFiles(pdf);
  await page.getByRole("button", { name: "Déposer cette pièce" }).click();
  await expect(
    page.getByText(
      "Pièce déposée ; elle est prête à être jointe à la réponse.",
    ),
  ).toBeVisible();
  await page
    .locator(".response-form textarea")
    .first()
    .fill("Affectation proposée : 1 000 unités au lot P1 et 1 000 au lot P2.");
  // Fixed-choice questions (e.g. a horizon confirmation left by an earlier journey on
  // this shared database) are answered with an allowed catalogue value.
  for (const choice of await page
    .locator(".response-form select:has(option[value=''])")
    .all())
    await choice.selectOption({ index: 1 });
  await page.locator(".allocation-input input").nth(0).fill("1000");
  await page.locator(".allocation-input input").nth(1).fill("1000");
  await page.getByRole("button", { name: "Transmettre la réponse" }).click();
  await expect(
    page.getByText("Réponse transmise à la revue de l’agent."),
  ).toBeVisible();

  // Human decision: the officer accepts document-backed evidence (double click = one revision).
  await page.getByRole("button", { name: "Agent", exact: true }).click();
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .click();
  await expect(page.getByText("Mises à jour internes")).toBeVisible();
  await expect(
    page.locator(".panel").filter({ hasText: "Mises à jour internes" }),
  ).toContainText("Réponse reçue");
  await page.getByRole("button", { name: "Dossiers", exact: true }).click();
  await expect(page.locator(".priority-ring strong")).toHaveText("20");
  await expect(page.getByText("Contributions au score")).toBeVisible();
  await expect(page.locator(".cause-value")).toHaveText("40 → 20");
  await expect(
    page.getByText("Réduction provisoire", { exact: true }),
  ).toBeVisible();
  // Company confirms source-backed fields; the service records the provisional 10 stage.
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  await page.getByRole("button", { name: "Confirmer les champs" }).click();
  await expect(
    page.getByText(
      "Champs vérifiés. Analyse mise à jour ; validation de l’agent requise.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Agent", exact: true }).click();
  await page.getByRole("button", { name: "Dossiers", exact: true }).click();
  await expect(page.locator(".priority-ring strong")).toHaveText("10");
  await expect(
    page.getByText("Validation agent requise", { exact: true }),
  ).toBeVisible();
  const accept = page.getByRole("button", { name: "Accepter dans ce dossier" });
  await expect(accept).toBeEnabled();
  await capture(
    page,
    "09_evidence_proposal.png",
    page.locator(".panel").filter({ has: accept }),
  );
  await accept.dblclick();
  await expect(
    page.getByRole("dialog", { name: "Nouvelle révision" }),
  ).toBeVisible();
  await expect(page.locator(".revision-grid")).toContainText("10");
  await expect(page.locator(".priority-ring strong")).toHaveText("0");
  await page.locator(".revision-card").evaluate(async (el) => {
    await Promise.all(el.getAnimations().map((a) => a.finished));
  });
  await capture(page, "10_revision_10_to_0.png");

  const caseView = await (
    await page.request.get("/api/cases/CASE-BRICKS-001", {
      headers: officerHeaders,
    })
  ).json();
  expect(
    caseView.requests.every(
      (r: { request: { origin: string } }) => r.request.origin === "AUTOMATIC",
    ),
  ).toBe(true); // nobody had to prepare a request by hand
  const history = await (
    await page.request.get("/api/cases/CASE-BRICKS-001/history", {
      headers: officerHeaders,
    })
  ).json();
  expect(
    history.revisions.filter((r: { reason: string }) =>
      r.reason.startsWith("Pièce acceptée"),
    ),
  ).toHaveLength(1);
  await page.getByRole("button", { name: "Continuer la revue" }).click();
  await page.getByRole("button", { name: "Avancé" }).click();
  await page.getByText("Timeline du dossier", { exact: true }).click();
  await expect(page.locator(".timeline li").first()).toContainText(
    "Version précédente",
  );
  await expect(
    page
      .locator(".panel")
      .filter({ hasText: "RÉVISIONS IMMUABLES" })
      .getByText("Indice de revue : 10 → 0"),
  ).toBeVisible();
  await capture(page, "11_history.png");
  await page.locator("summary").filter({ hasText: "Journal d’audit" }).click();
  const audit = page
    .locator(".panel")
    .filter({ hasText: "DÉCISIONS ET CALCULS ENREGISTRÉS" });
  await expect(audit).toContainText("EVIDENCE_ACCEPTED");
  await expect(audit).toContainText("Indice de revue : 10 → 0");
  await expect(audit).toContainText("Cause ");
  await expect(audit).toContainText("Règle :");
  await page.getByRole("button", { name: "Avancé" }).click();
  await page.getByText("Diagnostics", { exact: true }).click();
  await expect(page.getByText("Analyse assistée BOUSSLA")).toBeVisible();
  await capture(page, "13_diagnostics.png");
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 1280, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    await page.getByRole("button", { name: "Dossiers", exact: true }).click();
    const width = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    expect(width).toBeLessThanOrEqual(viewport.width);
  }
  await page.goto("/page-inconnue");
  await expect(
    page.getByRole("heading", { name: "Cette page n’existe pas." }),
  ).toBeVisible();
});

import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const shots = resolve("..", "docs", "screenshots", "react_ui");
const pdf = resolve(
  "..",
  "docs",
  "build_lock",
  "fixtures",
  "documents",
  "06_second_project_allocation.pdf",
);
const capture = async (
  page: import("@playwright/test").Page,
  name: string,
  fullPage = true,
) => {
  if (process.env.BOUSSLA_E2E_SCREENSHOTS !== "1") return;
  mkdirSync(shots, { recursive: true });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: resolve(shots, name), fullPage });
};

test("real company-to-officer review creates a 40 to 0 revision", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "File de revue" }),
  ).toBeVisible();
  await expect(page.locator(".queue-item .priority-number")).toHaveText("40");
  await capture(page, "04_officer_queue.png");
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Votre dossier, en un regard" }),
  ).toBeVisible();
  await expect(page.getByText("Priorité de revue")).toHaveCount(0);
  await capture(page, "01_company_overview.png");
  await page.getByRole("button", { name: "Opérations" }).click();
  await expect(
    page.getByRole("heading", { name: "Opérations observées" }),
  ).toBeVisible();
  await capture(page, "02_operations_documents.png");
  await page.getByRole("button", { name: "Contexte" }).click();
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
  await page.getByRole("button", { name: "Dossier", exact: true }).click();
  await expect(page.locator(".priority-ring strong")).toHaveText("40");
  await capture(page, "05_dossier_priority40.png");
  await page.getByRole("button", { name: "Références" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Passages de référence candidats à examiner",
    }),
  ).toBeVisible();
  await capture(page, "06_reference_panel.png");
  await page.getByRole("button", { name: "Dossier", exact: true }).click();
  await page.getByRole("button", { name: "Préparer la demande" }).click();
  await expect(
    page.getByRole("button", { name: "Publier dans la boîte de démo" }),
  ).toBeVisible();
  await capture(page, "07_clarification.png");
  // Double click: the client lock and server version checks allow one request only.
  await page
    .getByRole("button", { name: "Publier dans la boîte de démo" })
    .dblclick();
  await expect(
    page.getByText("Demande publiée dans la boîte de démonstration."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await page.getByRole("button", { name: "Pièces" }).click();
  await page.getByRole("button", { name: "Demandes" }).click();
  await page.getByRole("button", { name: "Répondre à la demande" }).click();
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
  await expect(page.locator(".response-form select").first()).not.toHaveValue(
    "",
  );
  await page.locator(".allocation-input input").nth(0).fill("1000");
  await page.locator(".allocation-input input").nth(1).fill("1000");
  await capture(page, "08_company_response_evidence.png");
  await page.getByRole("button", { name: "Transmettre la réponse" }).click();
  await expect(
    page.getByText("Réponse transmise à la revue de l’agent."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Agent", exact: true }).click();
  await page.getByRole("button", { name: "Dossier", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Accepter dans ce dossier" }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Accepter dans ce dossier" })
    .dblclick();
  await expect(
    page.getByRole("dialog", { name: "Nouvelle révision" }),
  ).toBeVisible();
  await expect(page.locator(".revision-grid")).toContainText("40");
  await expect(page.locator(".revision-grid")).toContainText("0");
  await expect(page.locator(".priority-ring strong")).toHaveText("0");
  await page.locator(".revision-card").evaluate(async (el) => {
    await Promise.all(
      el.getAnimations().map((animation) => animation.finished),
    );
  });
  await capture(page, "09_revision_40_to_0.png", false);
  const officerHeaders = { "X-Boussla-Demo-Role": "OFFICER" };
  const caseView = await (
    await page.request.get("/api/cases/CASE-BRICKS-001", {
      headers: officerHeaders,
    })
  ).json();
  expect(caseView.requests).toHaveLength(1);
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
  await expect(page.locator(".priority-ring strong")).toHaveText("0");
  await page.getByRole("button", { name: "Historique" }).click();
  await expect(page.locator(".timeline li").first()).toContainText(
    "Version précédente",
  );
  await capture(page, "10_history.png");
  await page.getByRole("button", { name: "Diagnostics" }).click();
  await capture(page, "11_diagnostics.png");
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 1280, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    await page.getByRole("button", { name: "Dossier", exact: true }).click();
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

import { test, expect, type Page } from "@playwright/test";
import { capture, skipSplash } from "./support";

const officer = { "X-Boussla-Demo-Role": "OFFICER" };

async function openEnterprise(page: Page, name: string) {
  await page.getByRole("button", { name: `Ouvrir ${name}` }).click();
  await page.getByRole("button", { name: "Historique", exact: true }).click();
  await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
}

test("boot splash plays once per session, then never blocks navigation", async ({
  page,
}) => {
  await page.goto("/");
  const splash = page.getByRole("status", { name: "Chargement de BOUSSLA" });
  await expect(splash).toBeVisible();
  await expect(splash.getByRole("img", { name: "BOUSSLA" })).toBeVisible();
  await page.waitForTimeout(2100); // mark drawn, wordmark and status lines visible
  await capture(page, "01_boot_brand.png", undefined, false, 0);
  await expect(splash).toHaveCount(0, { timeout: 3000 });
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toBeVisible();
  await expect(
    page.locator(".sidebar .brand img, .sidebar .brand svg").first(),
  ).toBeVisible();
  await page.reload();
  await expect(splash).toHaveCount(0);
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await expect(splash).toHaveCount(0);
});

test.describe("release journeys", () => {
  test.beforeEach(async ({ page }) => skipSplash(page));

  test("JOURNEY 1 — portfolio sorted by triage, Company 360, comparison, investigator", async ({
    page,
  }) => {
    await page.goto("/");
    const cards = page.locator(".portfolio-card-item");
    await expect(cards).toHaveCount(13);
    await expect(page.locator(".portfolio-count")).toHaveText("13 dossiers");
    const triage = (
      await page.locator(".portfolio-triage").allTextContents()
    ).map(Number);
    expect(triage).toEqual([...triage].sort((a, b) => b - a)); // server order
    await capture(page, "02_portfolio.png");

    await openEnterprise(page, "SYNTHÉTIQUE — Travaux Opale");
    await expect(page.locator(".month-bars > div")).toHaveCount(12);
    await expect(
      page.getByText("Divergences répétées entre observations").first(),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Instantané financier synthétique — source autorisée simulée",
      ),
    ).toBeVisible();
    await capture(page, "03_company_360.png");
    const comparison = page.locator(".comparison-card");
    await expect(
      comparison.getByText("Écart détecté entre les observations").first(),
    ).toBeVisible();
    await expect(
      comparison.locator(".comparison-difference").first(),
    ).toBeVisible();
    await capture(
      page,
      "04_buyer_seller_comparison.png",
      comparison.locator(".comparison-block").first(),
    );

    await page.getByRole("button", { name: "Dossiers", exact: true }).click();
    await page
      .locator("summary")
      .filter({ hasText: "Enquête détaillée et simulations" })
      .click();
    const brief = page.locator(".investigator-panel");
    await expect(
      brief.getByRole("heading", { name: "Analyse assistée BOUSSLA" }),
    ).toBeVisible();
    const hypotheses = page.locator(".hypothesis-card");
    expect(await hypotheses.count()).toBeGreaterThan(0);
    expect(await hypotheses.count()).toBeLessThanOrEqual(5);
    await expect(hypotheses.first()).toContainText("Support de l’hypothèse");
    await expect(page.locator("body")).not.toContainText(
      /fraude détectée|entreprise frauduleuse/i,
    );
    await capture(page, "06_investigator_hypotheses.png", brief);
  });

  test("JOURNEY 4 — activity gap raises triage, not the review index", async ({
    page,
  }) => {
    await page.goto("/");
    const card = page
      .locator(".portfolio-card-item")
      .filter({ hasText: "SYNTHÉTIQUE — Fournitures Dune" });
    await expect(card.locator(".portfolio-index")).toHaveText("0");
    expect(
      Number(await card.locator(".portfolio-triage").textContent()),
    ).toBeGreaterThan(0);
    await expect(
      card.getByText("Période sans activité à examiner"),
    ).toBeVisible();
    await openEnterprise(page, "SYNTHÉTIQUE — Fournitures Dune");
    await expect(
      page.getByText("Période sans activité documentée").first(),
    ).toBeVisible();
    await expect(
      page.getByText(/ni des constats ni des indices de fraude/),
    ).toBeVisible();
    const view = await (
      await page.request.get("/api/cases/SYN-OP-005-CASE", { headers: officer })
    ).json();
    expect(view.score.review_index).toBe(0);
    expect(view.triage.reason_codes).toContain("ACTIVITY_GAP_NEEDS_REVIEW");
    expect(
      view.findings.filter(
        (f: { status: string }) => f.status === "UNRESOLVED",
      ),
    ).toHaveLength(0);
  });

  test("JOURNEY 5 — no-project durable asset declared with project null", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Entreprise", exact: true }).click();
    await page.getByRole("button", { name: "Messages" }).click();
    await page.getByText("Contexte déclaré", { exact: true }).click();
    await page
      .getByLabel("Projet concerné")
      .selectOption({ label: "Aucun projet / usage général de l’entreprise" });
    await page.getByLabel("Catégorie d’usage").selectOption("LONG_LIVED_ASSET");
    await page
      .getByPlaceholder("Décrivez l’affectation prévue…")
      .fill(
        "Achat de trois véhicules pour la flotte commerciale de l'entreprise.",
      );
    await page.getByPlaceholder("Ex. projet P1").fill("Entreprise");
    await page
      .getByRole("button", { name: "Enregistrer la déclaration" })
      .click();
    await expect(
      page.getByText("Contexte déclaré et nouvelle version créée."),
    ).toBeVisible();
    const view = await (
      await page.request.get("/api/cases/CASE-BRICKS-001", {
        headers: { "X-Boussla-Demo-Role": "COMPANY" },
      })
    ).json();
    const claims = [...view.context_claims].sort((a, b) =>
      a.submitted_at.localeCompare(b.submitted_at),
    );
    const latest = claims[claims.length - 1];
    expect(latest.project_id).toBeNull();
    expect(latest.purpose_category).toBe("LONG_LIVED_ASSET");
  });

  test("JOURNEY 6 — demo operator adds, deletes and resets synthetic data", async ({
    page,
  }) => {
    page.on("dialog", (dialog) => dialog.accept());
    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "Données démo" }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Opérateur démo" }).click();
    await expect(
      page.getByText(
        "Administration de données synthétiques — démonstration locale.",
      ),
    ).toBeVisible();
    const rows = page.locator(".admin-list > div");
    await expect(rows).toHaveCount(12);
    await page.getByLabel("Nom").fill("Atelier Essai");
    await page.getByLabel("Secteur").fill("Services");
    await page.getByRole("button", { name: "Ajouter" }).click();
    await expect(
      page.getByText("Entreprise synthétique ajoutée au portefeuille."),
    ).toBeVisible();
    await expect(rows).toHaveCount(13);
    await capture(page, "12_admin.png");

    await page.getByRole("button", { name: "Agent", exact: true }).click();
    await expect(page.locator(".portfolio-card-item")).toHaveCount(14);
    await expect(page.getByText("SYNTHÉTIQUE — Atelier Essai")).toBeVisible();

    await page.getByRole("button", { name: "Opérateur démo" }).click();
    await rows
      .filter({ hasText: "SYNTHÉTIQUE — Atelier Essai" })
      .getByRole("button", { name: "Supprimer" })
      .click();
    await expect(rows).toHaveCount(12);
    await page
      .getByRole("button", { name: /Réinitialiser le portefeuille/ })
      .click();
    await expect(
      page.getByText("Portefeuille synthétique réinitialisé."),
    ).toBeVisible();
    await expect(rows).toHaveCount(12);
    const reset = await (
      await page.request.get("/api/cases/SYN-OP-001-CASE", { headers: officer })
    ).json();
    expect(reset.case_version).toBe(1);
    // The operator never becomes an officer or a company.
    const forbidden = await page.request.get("/api/officer/queue", {
      headers: { "X-Boussla-Demo-Role": "OPERATOR" },
    });
    expect(forbidden.status()).toBe(403);
    const brick = await page.request.get("/api/cases/CASE-BRICKS-001", {
      headers: { "X-Boussla-Demo-Role": "OPERATOR" },
    });
    expect(brick.status()).toBe(403);
  });
});

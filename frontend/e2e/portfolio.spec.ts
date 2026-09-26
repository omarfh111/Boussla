import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const shots = resolve("..", "docs", "screenshots", "final_portfolio_ui");
const capture = async (page: import("@playwright/test").Page, name: string) => {
  mkdirSync(shots, { recursive: true });
  await page.screenshot({ path: resolve(shots, name), fullPage: true });
};

test("current main portfolio opens a company 360 and keeps officer data scoped", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toBeVisible();
  await expect(page.locator(".portfolio-card-item")).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Triage le plus élevé" }),
  ).toBeDisabled();
  await capture(page, "01_officer_portfolio.png");

  await page.locator(".portfolio-open").first().click();
  await expect(page.locator(".company360")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Chronologie des factures" }),
  ).toBeVisible();
  await capture(page, "02_company_360.png");

  await page.getByRole("button", { name: "Dossier", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Analyse assistée BOUSSLA" }),
  ).toBeVisible();
  await expect(
    page.getByText(/n’a pas fourni d’InvestigatorBrief/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Scénarios de sensibilité" }),
  ).toBeVisible();
  await capture(page, "03_investigator_and_scenarios.png");

  await page.getByRole("button", { name: "Données démo" }).click();
  await expect(
    page.getByRole("heading", { name: "Administration de démonstration" }),
  ).toBeVisible();
  await expect(page.locator(".admin-list strong")).toHaveCount(1);
  await expect(page.locator(".admin-actions button").first()).toBeDisabled();
  await capture(page, "04_demo_admin_disabled.png");

  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Votre dossier, en un regard" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Analyse assistée BOUSSLA" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Données démo" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toHaveCount(0);
});

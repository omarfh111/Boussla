import { test, expect } from "@playwright/test";
import { skipSplash } from "./support";

const officer = { "X-Boussla-Demo-Role": "OFFICER" };
const company = { "X-Boussla-Demo-Role": "COMPANY" };
test.beforeEach(async ({ page }) => skipSplash(page));

test("evidence network remains officer scoped, filterable and inspectable", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toBeVisible();
  const response = await page.request.get("/api/network", { headers: officer });
  expect(response.ok()).toBe(true);
  const graph = await response.json();
  expect(graph.nodes.length).toBeGreaterThan(0);
  expect(graph.edges.length).toBeGreaterThan(0);
  expect(
    graph.edges.every(
      (edge: { source_ids: string[] }) => edge.source_ids.length > 0,
    ),
  ).toBe(true);
  expect(
    (await page.request.get("/api/network", { headers: company })).status(),
  ).toBe(403);
  const loaded = page.waitForResponse(
    (result) => result.url().includes("/api/network/case/") && result.ok(),
  );
  await page.getByRole("button", { name: "Réseau", exact: true }).click();
  await loaded;
  const visual = page.locator(".evidence-network");
  await expect(
    page.getByRole("heading", { name: "Réseau de preuves" }),
  ).toBeVisible();
  await expect(page.getByLabel("Périmètre du réseau")).toHaveValue("case");
  await expect(visual.locator("svg.network-map")).toBeVisible();
  const count = () =>
    visual
      .locator(".network-count")
      .textContent()
      .then((text) => Number(text?.match(/\d+/)?.[0]));
  const overviewCount = await count();
  await visual.getByLabel("Vue").selectOption("all");
  const allCount = await count();
  expect(allCount).toBeGreaterThan(overviewCount);
  await visual.getByText("Liste accessible des nœuds visibles").click();
  const firstCompany = visual
    .locator(".network-entity-list")
    .first()
    .getByRole("button")
    .filter({ hasText: "Entreprise" })
    .first();
  await firstCompany.focus();
  await page.keyboard.press("Enter");
  await expect(visual.getByLabel("Inspecteur du réseau")).toContainText(
    "Confiance opérationnelle",
  );
  await visual.getByText("Liste accessible des relations visibles").click();
  await visual
    .locator(".network-entity-list")
    .last()
    .getByRole("button")
    .first()
    .click();
  await expect(visual.getByLabel("Inspecteur du réseau")).toContainText(
    "Sources",
  );
  await visual.getByText("Filtres de faits").click();
  await visual.getByLabel("Montant minimum (TND)").fill("999999999");
  expect(await count()).toBeLessThan(allCount);
  await visual.getByLabel("Montant minimum (TND)").fill("");
  await visual.getByLabel("Depuis").fill("2030-01");
  expect(await count()).toBeLessThan(allCount);
  await visual.getByLabel("Depuis").fill("");
  const companyNode = graph.nodes.find(
    (node: { kind: string }) => node.kind === "COMPANY",
  );
  await visual.getByLabel("Rechercher une entreprise").fill(companyNode.label);
  expect(await count()).toBeLessThan(allCount);
  await visual.getByLabel("Rechercher une entreprise").fill("");
  await visual.getByLabel("Constats du dossier courant uniquement").check();
  expect(await count()).toBeLessThan(allCount);
  await visual.getByLabel("Constats du dossier courant uniquement").uncheck();
  await page.getByLabel("Périmètre du réseau").selectOption("all");
  await expect(visual.locator(".network-count")).not.toContainText("0 nœuds");
  await page.getByText("Signaux et relations détaillés").click();
  await expect(page.getByText("Relations entre entreprises")).toBeVisible();
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  expect(
    await page.getByRole("button", { name: "Réseau", exact: true }).count(),
  ).toBe(0);
});

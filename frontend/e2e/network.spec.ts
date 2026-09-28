import { test, expect } from "@playwright/test";
import { skipSplash } from "./support";

const officer = { "X-Boussla-Demo-Role": "OFFICER" };
const company = { "X-Boussla-Demo-Role": "COMPANY" };
test.beforeEach(async ({ page }) => skipSplash(page));

test("network relationships are source-backed and officer scoped", async ({
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
  const relation = graph.edges.find(
    (edge: { kind: string }) => edge.kind === "SELLS_TO",
  );
  expect(relation).toBeTruthy();
  await page.getByRole("button", { name: "Réseau", exact: true }).click();
  await expect(page.getByLabel("Périmètre du réseau")).toHaveValue("case");
  await expect(page.locator(".network-3d canvas")).toBeVisible();
  const caseNodes = Number(
    (await page.locator(".network-3d > p").first().textContent())?.match(
      /\d+/,
    )?.[0],
  );
  expect(caseNodes).toBeLessThan(graph.nodes.length);
  await page.getByLabel("Périmètre du réseau").selectOption("all");
  await expect(page.getByText("Relations entre entreprises")).toBeVisible();
  const source = graph.nodes.find(
    (node: { node_id: string }) => node.node_id === relation.source,
  );
  const target = graph.nodes.find(
    (node: { node_id: string }) => node.node_id === relation.target,
  );
  await expect(
    page.locator(".panel").filter({ hasText: "Relations entre entreprises" }),
  ).toContainText(`${source.label} → ${target.label}`);
  await expect(
    page.locator(".panel").filter({ hasText: "Relations entre entreprises" }),
  ).toContainText(relation.source_ids[0]);
  const visual = page.locator(".network-3d");
  const canvas = visual.getByRole("img", { name: /Réseau 3D rotatif/ });
  await expect(canvas).toBeVisible();
  await visual.getByRole("button", { name: "Zoom +" }).click();
  await visual.getByRole("button", { name: "Zoom −" }).click();
  const initialCount = Number(
    (await visual.locator(":scope > p").first().textContent())?.match(
      /\d+/,
    )?.[0],
  );
  await visual.getByLabel("Montant minimum (TND)").fill("999999999");
  const reducedCount = Number(
    (await visual.locator(":scope > p").first().textContent())?.match(
      /\d+/,
    )?.[0],
  );
  expect(reducedCount).toBeLessThan(initialCount);
  await visual.getByLabel("Montant minimum (TND)").fill("");
  await visual.getByLabel("Depuis").fill("2030-01");
  const futureCount = Number(
    (await visual.locator(":scope > p").first().textContent())?.match(
      /\d+/,
    )?.[0],
  );
  expect(futureCount).toBeLessThan(initialCount);
  await visual.getByLabel("Depuis").fill("");
  await visual.getByLabel("Rechercher une entreprise").fill(source.label);
  await expect(visual.locator(":scope > p").first()).not.toContainText(
    `${initialCount} nœuds`,
  );
  await visual.getByLabel("Rechercher une entreprise").fill("");
  await visual.getByLabel("Constats du dossier courant uniquement").check();
  await expect(visual.locator(":scope > p").first()).not.toContainText(
    `${initialCount} nœuds`,
  );
  await visual.getByLabel("Constats du dossier courant uniquement").uncheck();
  await visual.getByText("Liste accessible des nœuds visibles").click();
  await visual
    .locator(".network-edge-list")
    .first()
    .getByRole("button")
    .filter({ hasText: source.label })
    .first()
    .click();
  await expect(visual.locator(".network-selection")).toContainText(
    "Confiance opérationnelle",
  );
  await visual.getByText("Liste accessible des relations visibles").click();
  await visual
    .locator(".network-edge-list")
    .last()
    .getByRole("button")
    .first()
    .click();
  await expect(visual.locator(".network-selection")).toContainText("Sources :");
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box!.x + box!.width / 2 + 45,
    box!.y + box!.height / 2 + 30,
  );
  await page.mouse.up();
  await expect(canvas).toBeVisible();
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  expect(
    await page.getByRole("button", { name: "Réseau", exact: true }).count(),
  ).toBe(0);
});

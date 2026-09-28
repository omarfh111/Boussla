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
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  expect(
    await page.getByRole("button", { name: "Réseau", exact: true }).count(),
  ).toBe(0);
});

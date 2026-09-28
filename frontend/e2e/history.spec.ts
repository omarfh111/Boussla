import { test, expect } from "@playwright/test";
import { skipSplash } from "./support";

const officer = { "X-Boussla-Demo-Role": "OFFICER" };

test.beforeEach(async ({ page }) => skipSplash(page));

test("history compares an enterprise with its covered own baseline", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toBeVisible();
  const queue = await (
    await page.request.get("/api/officer/queue", { headers: officer })
  ).json();
  const selected = queue.items.find((item: { company_display_name: string }) =>
    item.company_display_name.includes("Travaux Opale"),
  );
  expect(selected).toBeTruthy();
  const view = await (
    await page.request.get(`/api/cases/${selected.case_id}`, {
      headers: officer,
    })
  ).json();
  const metric = view.behavior_profile?.metrics.find(
    (item: { status: string }) => item.status === "AVAILABLE",
  );
  expect(metric).toBeTruthy();
  await page
    .locator(".portfolio-card-item")
    .filter({ hasText: selected.case_id })
    .getByRole("button", { name: /Ouvrir/ })
    .click();
  await page.getByRole("button", { name: "Historique", exact: true }).click();
  await expect(page.getByText("Habitude vs période actuelle")).toBeVisible();
  const comparison = page
    .locator(".history-comparisons article")
    .filter({ hasText: metric.label_fr })
    .first();
  await expect(comparison).toContainText(metric.current_value);
  await expect(comparison).toContainText(metric.baseline_value);
  await expect(comparison).toContainText(
    `${metric.sample_size} mois exploitables`,
  );
  for (const month of view.monthly_activity.filter(
    (item: { coverage_status: string }) => item.coverage_status === "UNKNOWN",
  )) {
    await expect(
      page.getByTitle(`${month.month} : couverture inconnue`),
    ).toContainText("—");
  }
});

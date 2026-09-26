import { test, expect } from "@playwright/test";

// A browser holding version N must not silently act on a case another client moved to N+1.
test("stale revision is surfaced and refetched, never silently retried", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Dossier", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Préparer la demande" }),
  ).toBeVisible();

  const company = { "X-Boussla-Demo-Role": "COMPANY" };
  const view = await (
    await page.request.get("/api/cases/CASE-BRICKS-001", { headers: company })
  ).json();
  const other = await page.request.post("/api/cases/CASE-BRICKS-001/context", {
    headers: { ...company, "Idempotency-Key": `other-client-${Date.now()}` },
    data: {
      expected_version: view.case_version,
      context: {
        project_id: "P1",
        purpose_category: "CONSTRUCTION_PROJECT",
        purpose_text: "Mise à jour depuis un autre poste",
        beneficiary_type: "Projet P1",
      },
    },
  });
  expect(other.ok()).toBeTruthy();

  const prepares: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/clarifications/prepare"))
      prepares.push(r.url());
  });
  await page.getByRole("button", { name: "Préparer la demande" }).click();
  await expect(
    page.getByText("Le dossier a changé. Les données ont été actualisées."),
  ).toBeVisible();
  expect(prepares).toHaveLength(1); // surfaced, not retried
});

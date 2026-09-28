import { test, expect } from "@playwright/test";
import { skipSplash } from "./support";

test.beforeEach(async ({ page }) => skipSplash(page));

test("investigation assistant answers from cited case and network facts only for officers", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Portefeuille des entreprises" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Dossiers", exact: true }).click();
  const assistant = page
    .locator(".panel")
    .filter({ hasText: "Assistant d’investigation" });
  await assistant.getByRole("button", { name: "Examiner les sources" }).click();
  await expect(assistant.locator(".investigation-answer")).toContainText(
    "Urgence de traitement",
  );
  await expect(assistant.locator(".investigation-answer")).toContainText("+40");
  await expect(assistant.locator(".investigation-answer")).toContainText(
    "Sources citées",
  );
  await assistant
    .getByLabel("Question sur ce dossier")
    .fill("Quelles relations réseau ?");
  await assistant.getByRole("button", { name: "Examiner les sources" }).click();
  await expect(assistant.locator(".investigation-answer")).toContainText(
    "Relation enregistrée",
  );
  await expect(assistant.locator(".investigation-answer")).toContainText(
    "TRANSACTION",
  );
  const denied = await page.request.post(
    "/api/cases/CASE-BRICKS-001/investigate",
    {
      headers: { "X-Boussla-Demo-Role": "COMPANY" },
      data: { question: "Pourquoi prioritaire ?" },
    },
  );
  expect(denied.status()).toBe(403);
  await page.getByRole("button", { name: "Entreprise", exact: true }).click();
  await expect(page.getByText("Assistant d’investigation")).toHaveCount(0);
});

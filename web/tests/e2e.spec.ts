import { expect, test, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");

  await page.getByLabel(/Username/i).fill("admin");
  await page.getByLabel(/Password/i).fill("admin");
  await page.getByRole("button", { name: /Log in/i }).click();

  await expect(page).toHaveURL(/\/extract$/);
}

test("home page renders navigation links", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("link", { name: /Login/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Extract entities/i })).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Query the recipe knowledge graph/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Ask a recipe question \(RAG\)/i }),
  ).toBeVisible();
});

test("/extract renders entity spans for a known input", async ({ page }) => {
  await login(page);

  await page.locator("textarea").fill("Akira Kurosawa directed Seven Samurai in 1954.");
  await page.getByRole("button", { name: /Extract/i }).click();

  await expect(page.locator('[data-testid="entity-span"]').first()).toBeVisible({
    timeout: 10_000,
  });
});

test("/kg renders rows for a seeded question", async ({ page }) => {
  await login(page);

  await page.goto("/kg");
  await page.locator("input").fill("Find Sichuan recipes");
  await page.getByRole("button", { name: /Ask/i }).click();

  await expect(page.locator('[data-testid="kg-row"]').first()).toBeVisible({
    timeout: 10_000,
  });
});

test("/rag renders a cited answer", async ({ page }) => {
  await login(page);

  await page.goto("/rag");
  await page.locator("input").fill("How do I prep ginger for stir-fry?");
  await page.getByRole("button", { name: /Ask/i }).click();

  await expect(page.locator('[data-testid="citation-marker"]').first()).toBeVisible({
    timeout: 30_000,
  });
});

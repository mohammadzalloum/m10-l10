import { expect, test, type Page } from "@playwright/test";

async function mockBackend(page: Page) {
  await page.route("**/extract", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        text: "Akira Kurosawa directed Seven Samurai in 1954.",
        entities: [
          {
            text: "Akira Kurosawa",
            label: "PERSON",
            start: 0,
            end: 14,
          },
          {
            text: "Seven Samurai",
            label: "WORK_OF_ART",
            start: 24,
            end: 37,
          },
          {
            text: "1954",
            label: "DATE",
            start: 41,
            end: 45,
          },
        ],
      }),
    });
  });

  await page.route("**/kg/query", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        cypher: "MATCH (r:Recipe)-[:HAS_CUISINE]->(:Cuisine {name: 'Sichuan'}) RETURN r.name AS recipe",
        rows: [
          {
            recipe: "Mapo Tofu",
            cuisine: "Sichuan",
          },
        ],
        count: 1,
      }),
    });
  });

  await page.route("**/rag/answer", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Peel or scrape the ginger, then mince or grate it before stir-frying. [1]",
        citations: [
          {
            chunk_id: "ginger-prep",
            score: 0.92,
            text: "Ginger can be peeled, minced, grated, and added early to hot oil.",
          },
        ],
        confidence: 0.92,
      }),
    });
  });
}

test("/ landing page lists three demo links", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("link", { name: /Extract entities/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /knowledge graph/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /RAG/i })).toBeVisible();
});

test("/extract renders entity spans for a known input", async ({ page }) => {
  await mockBackend(page);

  await page.goto("/extract");
  await page.locator("textarea").fill("Akira Kurosawa directed Seven Samurai in 1954.");
  await page.getByRole("button", { name: /Extract/i }).click();

  await expect(page.locator('[data-testid="entity-span"]').first()).toBeVisible({
    timeout: 10_000,
  });
});

test("/kg renders rows for a seeded question", async ({ page }) => {
  await mockBackend(page);

  await page.goto("/kg");
  await page.locator("input").fill("Find Sichuan recipes");
  await page.getByRole("button", { name: /Ask/i }).click();

  await expect(page.locator('[data-testid="kg-row"]').first()).toBeVisible({
    timeout: 10_000,
  });
});

test("/rag renders a cited answer", async ({ page }) => {
  await mockBackend(page);

  await page.goto("/rag");
  await page.locator("input").fill("How do I prep ginger for stir-fry?");
  await page.getByRole("button", { name: /Ask/i }).click();

  await expect(page.locator('[data-testid="citation-marker"]').first()).toBeVisible({
    timeout: 30_000,
  });
});

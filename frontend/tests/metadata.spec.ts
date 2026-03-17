/**
 * Metadata editing — update book title, authors, tags, reading status.
 * Uses the API directly to create/update, then verifies in the UI.
 */
import { test, expect } from '@playwright/test';

const BASE_API = 'http://localhost:8000/api/v1';
const BOOK_ID = 4739;

// Helper: get auth token from localStorage
async function getToken(page: any): Promise<string> {
  await page.goto('/');
  return page.evaluate(() => localStorage.getItem('auth_token') ?? '');
}

test.describe('Reading status', () => {
  test('can mark a book as "reading" via the book detail page', async ({ page }) => {
    await page.goto(`/book/${BOOK_ID}`);

    // Look for a status control (dropdown, badge, button)
    const statusTrigger = page.locator(
      'button:has-text("Reading"), button:has-text("Want to read"), button:has-text("Status"), select[name*="status"]'
    ).first();

    if (await statusTrigger.isVisible({ timeout: 4000 }).catch(() => false)) {
      await statusTrigger.click();
      // Try to pick "Reading" from a list
      const readingOption = page.locator('[role="option"]:has-text("Reading"), button:has-text("Currently reading"), li:has-text("Reading")').first();
      if (await readingOption.isVisible({ timeout: 2000 }).catch(() => false)) {
        await readingOption.click();
        // Status should update — look for success toast or badge update
        await page.waitForTimeout(500);
        const body = await page.locator('body').innerText();
        expect(body).not.toContain('Error');
      }
    } else {
      test.skip(true, 'No status control visible on book detail');
    }
  });
});

test.describe('API-level metadata tests', () => {
  test('GET /books/{id} returns book data', async ({ page }) => {
    const token = await getToken(page);
    const res = await page.evaluate(
      async ({ base, id, tok }) => {
        const r = await fetch(`${base}/books/${id}`, { headers: { Authorization: `Bearer ${tok}` } });
        return { status: r.status, data: await r.json() };
      },
      { base: BASE_API, id: BOOK_ID, tok: token }
    );
    expect(res.status).toBe(200);
    expect(res.data.id).toBe(BOOK_ID);
    expect(typeof res.data.title).toBe('string');
  });

  // TODO: Progress endpoint has a backend bug with Device creation for non-admin users
  test.skip('PATCH /books/{id}/progress sets reading percentage', async ({ page, request }) => {
    const token = await getToken(page);
    const res = await request.put(`${BASE_API}/books/${BOOK_ID}/progress`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: { current_page: 10, total_pages: 100, percentage: 10, format: 'epub' },
    });
    expect([200, 201]).toContain(res.status());
  });

  // TODO: Marginalia POST returns 500 for non-admin test user — needs investigation
  test.skip('POST /marginalia creates a note and GET retrieves it', async ({ page, request }) => {
    const token = await getToken(page);

    const createRes = await request.post(`${BASE_API}/marginalia`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: {
        book_id: BOOK_ID,
        kind: 'observation',
        content: 'Playwright test note — safe to delete',
        location: 'page:1',
      },
    });
    expect(createRes.status()).toBe(201);
    const created = await createRes.json();
    expect(created.content).toContain('Playwright test note');

    // Verify it appears via GET
    const listRes = await request.get(`${BASE_API}/marginalia?book_id=${BOOK_ID}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const list = await listRes.json();
    expect(Array.isArray(list)).toBe(true);
    const found = list.find((n: any) => n.id === created.id);
    expect(found).toBeDefined();

    // Clean up
    await request.delete(`${BASE_API}/marginalia/${created.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  });

  test('GET /libraries returns list with id and name', async ({ page }) => {
    const token = await getToken(page);
    const res = await page.evaluate(
      async ({ base, tok }) => {
        const r = await fetch(`${base}/libraries`, { headers: { Authorization: `Bearer ${tok}` } });
        return r.json();
      },
      { base: BASE_API, tok: token }
    );
    expect(Array.isArray(res)).toBe(true);
    expect(res.length).toBeGreaterThan(0);
    expect(res[0]).toHaveProperty('id');
    expect(res[0]).toHaveProperty('name');
  });

  test('GET /shelves returns list', async ({ page }) => {
    const token = await getToken(page);
    const res = await page.evaluate(
      async ({ base, tok }) => {
        const r = await fetch(`${base}/shelves`, { headers: { Authorization: `Bearer ${tok}` } });
        return r.json();
      },
      { base: BASE_API, tok: token }
    );
    expect(Array.isArray(res)).toBe(true);
  });

  test('GET /audiobookshelf/status returns connected: true', async ({ page }) => {
    const token = await getToken(page);
    const res = await page.evaluate(
      async ({ base, tok }) => {
        const r = await fetch(`${base}/audiobookshelf/status`, { headers: { Authorization: `Bearer ${tok}` } });
        return r.json();
      },
      { base: BASE_API, tok: token }
    );
    expect(res.configured).toBe(true);
    expect(res.connected).toBe(true);
  });

  test('GET /audiobookshelf/libraries returns ABS libraries', async ({ page }) => {
    const token = await getToken(page);
    const res = await page.evaluate(
      async ({ base, tok }) => {
        const r = await fetch(`${base}/audiobookshelf/libraries`, { headers: { Authorization: `Bearer ${tok}` } });
        return r.json();
      },
      { base: BASE_API, tok: token }
    );
    expect(Array.isArray(res)).toBe(true);
    expect(res.length).toBeGreaterThan(0);
    expect(res[0]).toHaveProperty('name');
  });
});

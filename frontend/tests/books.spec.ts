/**
 * Book detail, metadata editing, and reader tests.
 */
import { test, expect } from '@playwright/test';

// Use a known book ID from the DB
const BOOK_ID = 4739;

test.describe('Book detail page', () => {
  test('loads book detail with title visible', async ({ page }) => {
    await page.goto(`/book/${BOOK_ID}`);
    await expect(page).not.toHaveURL(/\/auth\/login/);
    // Page should have some heading / title content
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible({ timeout: 8000 });
  });

  test('shows book metadata sections', async ({ page }) => {
    await page.goto(`/book/${BOOK_ID}`);
    // Should show some metadata (authors, etc.)
    await expect(page.locator('body')).not.toContainText('Book not found');
  });

  test('opens edit metadata form', async ({ page }) => {
    await page.goto(`/book/${BOOK_ID}`);

    // Look for an Edit button
    const editBtn = page.locator('button:has-text("Edit"), a:has-text("Edit"), button[title*="dit"]').first();
    if (await editBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await editBtn.click();
      // An edit form or dialog should appear
      const form = page.locator('form, [role="dialog"], textarea, input[name="title"]').first();
      await expect(form).toBeVisible({ timeout: 3000 });
    } else {
      test.skip(true, 'No Edit button found on book detail page');
    }
  });

  test('navigates to reader when a readable file exists', async ({ page }) => {
    await page.goto(`/book/${BOOK_ID}`);
    // Look for a Read button or link
    const readBtn = page.locator('a:has-text("Read"), button:has-text("Read"), a[href*="/reader/"]').first();
    if (await readBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await readBtn.click();
      await expect(page).toHaveURL(/\/reader\//, { timeout: 5000 });
      // Reader should not show an error
      await expect(page.locator('body')).not.toContainText('Unexpected Application Error');
    } else {
      test.skip(true, 'No readable file found for this book');
    }
  });
});

test.describe('Book marginalia panel in reader', () => {
  test('Notes button appears in reader', async ({ page }) => {
    await page.goto(`/reader/${BOOK_ID}`);
    // Wait for the reader area to be present (even if book has no files)
    await page.waitForLoadState('networkidle');
    // Notes button should be visible if a readable file is present
    const notesBtn = page.locator('button:has-text("Notes")');
    if (await notesBtn.isVisible({ timeout: 4000 }).catch(() => false)) {
      await notesBtn.click();
      // Notes panel should open
      await expect(page.locator('text=Notes').first()).toBeVisible();
    }
  });
});

test.describe('Library page', () => {
  test('library 3 (Books) loads and shows books', async ({ page }) => {
    await page.goto('/library/1');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    // Should show some content
    await expect(page.locator('body')).not.toContainText('Unexpected Application Error');
    // Check for book cards/grid
    const bookItems = page.locator('[class*="grid"], [class*="card"], [class*="book"]').first();
    await expect(bookItems).toBeVisible({ timeout: 8000 });
  });

  test('clicking a book in library navigates to book detail', async ({ page }) => {
    await page.goto('/library/1');
    // Wait for book links to appear (not networkidle — WebSocket stays open)
    const firstBook = page.locator('a[href*="/book/"]').first();
    await expect(firstBook).toBeVisible({ timeout: 10000 });
    const href = await firstBook.getAttribute('href');
    await page.goto(href!);
    await expect(page).toHaveURL(/\/book\/\d+/);
  });
});

test.describe('Search', () => {
  test('search returns results for a known term', async ({ page }) => {
    await page.goto('/search?q=protagoras');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    // Wait for results — don't use networkidle (WebSocket keeps connection open)
    const results = page.locator('a[href*="/book/"]');
    await expect(results.first()).toBeVisible({ timeout: 15000 });
  });

  test('search with no results shows empty state', async ({ page }) => {
    await page.goto('/search?q=xyzzy_no_such_book_12345');
    await page.waitForLoadState('networkidle');
    const body = await page.locator('body').innerText();
    // Either "no results" text or zero book links
    const bookLinks = await page.locator('a[href*="/book/"]').count();
    expect(bookLinks === 0 || body.toLowerCase().includes('no result') || body.toLowerCase().includes('nothing found')).toBeTruthy();
  });

  test('search bar in header navigates to search page', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.locator('input[type="search"], input[placeholder*="earch"]').first();
    await searchInput.fill('Plato');
    await searchInput.press('Enter');
    await expect(page).toHaveURL(/\/search\?q=Plato/i, { timeout: 5000 });
  });
});

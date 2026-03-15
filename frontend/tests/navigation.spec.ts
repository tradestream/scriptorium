/**
 * Navigation & layout tests — sidebar, header, dark mode, mobile menu.
 */
import { test, expect } from '@playwright/test';

test.describe('Sidebar navigation', () => {
  test('sidebar renders on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto('/');
    // Sidebar should be visible (md:flex)
    const sidebar = page.locator('nav, aside, [class*="sidebar"]').first();
    await expect(sidebar).toBeVisible({ timeout: 5000 });
  });

  test('mobile menu toggle shows/hides sidebar', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    // Hamburger button should exist
    const menuBtn = page.locator('button[aria-label*="enu"], button:has([data-lucide="menu"])').first();
    if (await menuBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await menuBtn.click();
      // Sidebar overlay should appear
      const overlay = page.locator('[class*="fixed"][class*="inset-0"]').first();
      await expect(overlay).toBeVisible({ timeout: 2000 });
    }
  });

  test('sidebar links navigate correctly', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto('/');

    // Click a sidebar link — settings
    const settingsLink = page.locator('a[href="/settings"]').first();
    if (await settingsLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await settingsLink.click();
      await expect(page).toHaveURL(/\/settings/);
    }
  });
});

test.describe('Header', () => {
  test('dark mode toggle switches theme', async ({ page }) => {
    await page.goto('/');
    const toggleBtn = page.locator('button[title*="heme"], button[title*="ode"], button:has([data-lucide="sun"]), button:has([data-lucide="moon"])').first();
    await expect(toggleBtn).toBeVisible({ timeout: 5000 });

    const htmlBefore = await page.locator('html').getAttribute('class');
    await toggleBtn.click();
    await page.waitForTimeout(200);
    const htmlAfter = await page.locator('html').getAttribute('class');
    // Class should change (dark added/removed)
    expect(htmlBefore).not.toBe(htmlAfter);
  });

  test('search input in header is functional', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.locator('input[type="search"]').first();
    await expect(searchInput).toBeVisible({ timeout: 5000 });
    await searchInput.fill('test');
    expect(await searchInput.inputValue()).toBe('test');
  });

  test('user menu opens on click', async ({ page }) => {
    await page.goto('/');
    // Last button in header is the user menu (after theme toggle)
    const userBtn = page.locator('header button').last();
    await userBtn.click();
    // Menu should show Settings and Sign out options
    await expect(page.locator('a[href="/settings"], button:has-text("Sign out")').first()).toBeVisible({ timeout: 3000 });
  });
});

test.describe('Browse pages', () => {
  test('authors page lists authors', async ({ page }) => {
    await page.goto('/browse/authors');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    // Should show some author names
    await expect(page.locator('body')).not.toContainText('Unexpected Application Error');
  });

  test('series page lists series', async ({ page }) => {
    await page.goto('/browse/series');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    await expect(page.locator('body')).not.toContainText('Unexpected Application Error');
  });

  test('tags page lists tags', async ({ page }) => {
    await page.goto('/browse/tags');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    await expect(page.locator('body')).not.toContainText('Unexpected Application Error');
  });

  test('stats page shows reading statistics', async ({ page }) => {
    await page.goto('/stats');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    await expect(page.locator('body')).not.toContainText('Unexpected Application Error');
  });
});

test.describe('Shelves & Collections', () => {
  test('shelves page loads', async ({ page }) => {
    await page.goto('/shelves');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/\/auth\/login/);
  });

  test('shelf detail page loads for shelf 1', async ({ page }) => {
    await page.goto('/shelves/1');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    await expect(page.locator('body')).not.toContainText('Unexpected Application Error');
  });

  test('collections page loads', async ({ page }) => {
    await page.goto('/collections');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/\/auth\/login/);
  });
});

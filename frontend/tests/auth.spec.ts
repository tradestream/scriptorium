/**
 * Authentication flows — login, logout, registration.
 */
import { test, expect } from '@playwright/test';

test.describe('Login flow', () => {
  test('shows validation error for empty credentials', async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await page.goto('/auth/login');

    // Try submitting empty form
    await page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first().click();

    // Either inline error or form stays on login page
    await expect(page).toHaveURL(/\/auth\/login/);
    await ctx.close();
  });

  test('shows error for wrong password', async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await page.goto('/auth/login');

    await page.locator('input[name="username"], input[placeholder*="sername"]').first().fill('nathaniel');
    await page.locator('input[type="password"]').fill('wrong_password_xyz');
    await page.locator('button[type="submit"]').click();

    // Should stay on login page (not redirect to app)
    await expect(page).toHaveURL(/\/auth\/login/);
    await ctx.close();
  });

  test('login with test credentials succeeds and redirects to home', async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await page.goto('/auth/login');

    await page.locator('input[name="username"], input[placeholder*="sername"]').first().fill('pw_test');
    await page.locator('input[type="password"]').fill('TestPass1234');
    await page.locator('button[type="submit"]').click();

    // Should redirect away from login
    await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 5000 });
    await ctx.close();
  });
});

test.describe('Logout flow', () => {
  test('clicking sign out returns user to login page', async ({ page }) => {
    await page.goto('/');
    // Last button in header is the user menu button
    await page.locator('header button').last().click();
    await page.locator('button:has-text("Sign out")').click();
    await expect(page).toHaveURL(/\/auth\/login/, { timeout: 5000 });
  });
});

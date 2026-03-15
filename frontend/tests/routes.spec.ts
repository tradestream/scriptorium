/**
 * Route smoke tests — every page should load without a crash or redirect to /auth/login.
 */
import { test, expect } from '@playwright/test';

// Routes that should render for an authenticated user
const APP_ROUTES = [
  { path: '/', label: 'Home' },
  { path: '/search?q=test', label: 'Search' },
  { path: '/add', label: 'Add content' },
  { path: '/library/1', label: 'Library detail (Academic)' },
  { path: '/browse/authors', label: 'Authors browse' },
  { path: '/browse/series', label: 'Series browse' },
  { path: '/browse/tags', label: 'Tags browse' },
  { path: '/shelves', label: 'Shelves list' },
  { path: '/collections', label: 'Collections list' },
  { path: '/stats', label: 'Stats' },
  { path: '/annotations', label: 'Annotations' },
  { path: '/marginalia', label: 'Marginalia' },
  { path: '/notebooks', label: 'Notebooks' },
  { path: '/settings', label: 'Settings' },
  { path: '/settings/kobo', label: 'Kobo settings' },
  { path: '/metadata', label: 'Metadata' },
  { path: '/duplicates', label: 'Duplicates' },
  { path: '/loose-leaves', label: 'Loose Leaves' },
];

for (const { path, label } of APP_ROUTES) {
  test(`${label} (${path}) loads without error`, async ({ page }) => {
    await page.goto(path);

    // Should NOT be redirected to login
    await expect(page).not.toHaveURL(/\/auth\/login/);

    // Should not show a hard error boundary / unhandled crash
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toContain('Unexpected Application Error');
    expect(bodyText).not.toContain('500');
  });
}

test('unauthenticated users are redirected to /auth/login', async ({ browser }) => {
  // Use a fresh context with no auth state
  const context = await browser.newContext({ storageState: undefined });
  const page = await context.newPage();
  await page.goto('/');
  await expect(page).toHaveURL(/\/auth\/login/);
  await context.close();
});

test('auth/login page renders correctly', async ({ browser }) => {
  const context = await browser.newContext({ storageState: undefined });
  const page = await context.newPage();
  await page.goto('/auth/login');
  await expect(page.locator('form, input[type="password"]').first()).toBeVisible();
  await context.close();
});

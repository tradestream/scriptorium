/**
 * Global setup — runs once before all tests.
 * Creates a test user (idempotent) and saves auth state to disk.
 */
import { chromium } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FRONTEND_URL = process.env.PLAYWRIGHT_FRONTEND_URL ?? 'http://localhost:5173';
const BACKEND_URL = process.env.PLAYWRIGHT_BACKEND_URL ?? 'http://localhost:8000';
const BASE = `${BACKEND_URL}/api/v1`;
const TEST_USER = { username: 'pw_test', email: 'pw_test@scriptorium.app', password: 'TestPass1234' };

async function apiPost(url: string, body: object, token?: string) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: res.status, body: await res.json() };
}

export default async function globalSetup() {
  // Ensure auth dir exists
  const authDir = path.join(__dirname, '.auth');
  fs.mkdirSync(authDir, { recursive: true });

  // Try login first (user may already exist)
  let tokenRes = await apiPost(`${BASE}/auth/login`, {
    username: TEST_USER.username,
    password: TEST_USER.password,
  });

  if (tokenRes.status !== 200) {
    // Register the user
    const regRes = await apiPost(`${BASE}/auth/register`, TEST_USER);
    if (regRes.status !== 201 && regRes.status !== 200) {
      throw new Error(`Failed to create test user: ${JSON.stringify(regRes.body)}`);
    }
    tokenRes = await apiPost(`${BASE}/auth/login`, {
      username: TEST_USER.username,
      password: TEST_USER.password,
    });
  }

  if (tokenRes.status !== 200) {
    throw new Error(`Login failed: ${JSON.stringify(tokenRes.body)}`);
  }

  const token = tokenRes.body.access_token as string;

  // Use Playwright to save auth state (localStorage token) to disk
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  // Navigate to the app and set the token in localStorage
  await page.goto(`${FRONTEND_URL}/auth/login`);
  await page.evaluate((t) => {
    localStorage.setItem('auth_token', t);
  }, token);

  // Save storage state
  await context.storageState({ path: path.join(authDir, 'user.json') });
  await browser.close();

  console.log(`✓ Test user "${TEST_USER.username}" authenticated`);
}

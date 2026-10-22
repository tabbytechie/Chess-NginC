import { readFileSync } from 'node:fs';

import { expect, test, type Page } from '@playwright/test';

/**
 * Full human-vs-engine play loop against the composed stack (Phase 5 e2e):
 * register → log out → log in → start a computer game as White → confirm the
 * engine replies in the same step → resign → the dashboard records the result
 * → export valid PGN. This is the only test that exercises all three services
 * together, so it runs against a real deployment (see playwright.config.ts).
 */
const PASSWORD = 'e2e-passw0rd';

function uniqueEmail(): string {
  return `e2e-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}@example.com`;
}

async function fillCredentials(page: Page, email: string, password: string): Promise<void> {
  await page.getByLabel('Email').fill(email);
  await page.getByLabel(/Password/).fill(password);
}

async function register(page: Page, email: string): Promise<void> {
  await page.goto('/register');
  await fillCredentials(page, email, PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Chess NginC' })).toBeVisible();
}

/** Choose a computer game as White on Easy (fastest deterministic reply). */
async function startEasyGameAsWhite(page: Page): Promise<void> {
  await page.getByRole('radio', { name: /Player vs Computer/ }).click();
  await page.getByRole('radio', { name: /White/ }).click();
  await page.getByRole('radio', { name: /Easy/ }).click();
  await page.getByRole('button', { name: /Start Easy battle/ }).click();
  await expect(page).toHaveURL(/\/games\/\d+$/);
}

test('a signed-in player completes a full game against the engine', async ({ page }) => {
  const email = uniqueEmail();
  await register(page, email);

  // Log out, then back in — proves the session cookie round-trips.
  await page.getByRole('button', { name: 'Log out' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await fillCredentials(page, email, PASSWORD);
  await page.getByRole('button', { name: 'Log in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Chess NginC' })).toBeVisible();

  await startEasyGameAsWhite(page);

  // Play 1. e4. In computer mode the engine's reply rides back in the same
  // response, so one row of the move history holds both plies and control
  // returns to White without a second click.
  await page.getByRole('gridcell', { name: /^e2,/ }).click();
  await page.getByRole('gridcell', { name: /^e4,/ }).click();
  const history = page.getByRole('list', { name: 'move history' });
  await expect(history.getByRole('listitem')).toHaveCount(1);
  await expect(page.getByRole('status').filter({ hasText: 'Turn: White' })).toBeVisible();

  // Resign: the banner shows the recorded result attributed against the player.
  await page.getByRole('button', { name: 'Resign' }).click();
  await expect(page.getByText('Resigned — game over')).toBeVisible();
  await expect(page.getByText(/Result: 0-1/)).toBeVisible();

  // Export PGN as a real download and assert it carries the result + played move.
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: /Download PGN/ }).click(),
  ]);
  const pgnPath = await download.path();
  if (!pgnPath) throw new Error('PGN download produced no file to inspect');
  const pgn = readFileSync(pgnPath, 'utf-8');
  expect(pgn).toContain('[Result "0-1"]');
  expect(pgn).toMatch(/1\. e4/);

  // The dashboard now lists the finished game with its resolved status.
  await page.getByRole('link', { name: /All games/ }).click();
  await expect(page.getByRole('link', { name: /resigned/ })).toBeVisible();
});

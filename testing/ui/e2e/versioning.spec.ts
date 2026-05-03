import { test, expect } from '@playwright/test';

test.describe('Version Management', () => {
  let dataId: string;

  test.beforeAll(async ({ browser }) => {
    // Create test data with multiple versions
    const page = await browser.newPage();
    await page.goto('/');
    
    // Create initial data
    const initialContent = JSON.stringify({ version: 1 }, null, 2);
    await page.locator('textarea[placeholder*="JSON"]').fill(initialContent);
    await page.click('button:has-text("Upload Data")');
    await expect(page.locator('.alert-success')).toBeVisible();
    
    // Wait and get data ID
    await page.waitForTimeout(1000);
    await page.locator('table tbody tr').first().click();
    const url = page.url();
    dataId = url.split('/').pop()!;
    
    // Create version 2
    await page.click('button:has-text("Edit")');
    await page.locator('textarea').fill(JSON.stringify({ version: 2 }, null, 2));
    await page.click('button:has-text("Save Changes")');
    await expect(page.locator('.alert-success')).toBeVisible();
    
    // Create version 3
    await page.click('button:has-text("Edit")');
    await page.locator('textarea').fill(JSON.stringify({ version: 3 }, null, 2));
    await page.click('button:has-text("Save Changes")');
    await expect(page.locator('.alert-success')).toBeVisible();
    
    await page.close();
  });

  test('should display version history', async ({ page }) => {
    await page.goto(`/data/${dataId}`);
    
    // Check version history sidebar
    await expect(page.locator('h3:has-text("Version History")')).toBeVisible();
    
    // Should have 3 versions
    const versionCards = page.locator('div[style*="border"]:has-text("v")');
    await expect(versionCards).toHaveCount(3);
    
    // Current version should be marked
    await expect(page.locator('span:has-text("CURRENT")')).toBeVisible();
  });

  test('should switch between versions', async ({ page }) => {
    await page.goto(`/data/${dataId}`);
    
    // Current version should be v3
    await expect(page.locator('h2')).toContainText('v3');
    await expect(page.locator('pre')).toContainText('"version": 3');
    
    // Click on version 2
    await page.locator('div:has-text("v2")').first().click();
    
    // Content should update
    await expect(page.locator('h2')).toContainText('v2');
    await expect(page.locator('pre')).toContainText('"version": 2');
    
    // Should show read-only indicator
    await expect(page.locator('span:has-text("Read-only")')).toBeVisible();
    
    // Edit button should not be visible for old versions
    await expect(page.locator('button:has-text("Edit")')).not.toBeVisible();
    
    // Click on version 1
    await page.locator('div:has-text("v1")').first().click();
    
    // Content should update
    await expect(page.locator('pre')).toContainText('"version": 1');
  });

  test('should show version metadata', async ({ page }) => {
    await page.goto(`/data/${dataId}`);
    
    // Check version cards have metadata
    const firstVersion = page.locator('div[style*="border"]:has-text("v3")').first();
    
    // Should show size
    await expect(firstVersion).toContainText(/\d+\s*(Bytes|KB)/);
    
    // Should show timestamp
    await expect(firstVersion).toContainText(/\d{1,2}\/\d{1,2}\/\d{4}/);
    
    // Should show content type
    await expect(firstVersion).toContainText('application/json');
  });

  test('should only allow editing current version', async ({ page }) => {
    await page.goto(`/data/${dataId}`);
    
    // On current version, Edit button should be visible
    await expect(page.locator('button:has-text("Edit")')).toBeVisible();
    
    // Switch to old version
    await page.locator('div:has-text("v1")').first().click();
    
    // Edit button should not be visible
    await expect(page.locator('button:has-text("Edit")')).not.toBeVisible();
  });
});

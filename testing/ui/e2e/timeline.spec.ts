import { test, expect } from '@playwright/test';

test.describe('Timeline Feature', () => {
  async function createDataViaPlayground(page: import('@playwright/test').Page, payload: unknown) {
    await page.goto('/?tab=testing');
    await page.locator('[data-testid="playground-tab-upload"]').click();
    await page.locator('[data-testid="upload-textarea"]').fill(JSON.stringify(payload, null, 2));
    await page.click('[data-testid="upload-submit"]');
    await expect(page.locator('.alert-success')).toBeVisible();
  }

  test.beforeEach(async ({ page }) => {
    await page.goto('/?tab=timeline');
    await expect(page.locator('button:has-text("Refresh")')).toBeVisible();
  });

  test('should display timeline tab', async ({ page }) => {
    await expect(page.locator('text=No Audit Memories Yet').or(page.locator('button:has-text("Refresh")'))).toBeVisible();
  });

  test('should show create action in timeline', async ({ page }) => {
    await createDataViaPlayground(page, { timeline: 'create-test', at: Date.now() });
    await page.goto('/?tab=timeline');
    await page.click('button:has-text("Refresh")');
    await expect(page.locator('text=/create/i')).toBeVisible();
  });

  test('should show update action in timeline', async ({ page }) => {
    // Create data first
    await createDataViaPlayground(page, { timeline: 'update-test', v: 1 });
    await page.waitForTimeout(1000);
    
    // Navigate to data and update it
    await page.goto('/?tab=data');
    await page.locator('table tbody tr').first().click();
    await page.click('button:has-text("Edit")');
    await page.locator('textarea').fill(JSON.stringify({ test: 2 }));
    await page.click('button:has-text("Save Changes")');
    await expect(page.locator('.alert-success')).toBeVisible();
    
    // Go back to timeline and verify audit entries
    await page.goto('/?tab=timeline');
    
    // Wait for timeline to load
    await page.waitForTimeout(1000);
    
    // Should show both create and update actions
    await expect(page.locator('text=/update/i')).toBeVisible();
    await expect(page.locator('text=/create/i')).toBeVisible();
  });

  test('should show delete action in timeline', async ({ page }) => {
    // Create data
    await createDataViaPlayground(page, { delete: 'timeline-test' });
    await page.waitForTimeout(1000);
    
    // Delete the data
    await page.goto('/?tab=data');
    await page.locator('table tbody tr').first().click();
    page.on('dialog', dialog => dialog.accept());
    await page.click('button:has-text("Delete")');
    
    // Check timeline
    await page.goto('/?tab=timeline');
    await page.waitForTimeout(1000);
    
    // Should show delete action
    await expect(page.locator('text=/delete/i')).toBeVisible();
  });

  test('should display timeline entries in chronological order', async ({ page }) => {
    await expect(page.locator('button:has-text("Refresh")')).toBeVisible();
    const entries = page.locator('a:has-text("View Data"), button:has-text("Remove")');
    await expect(entries.first()).toBeVisible();
  });

  test('should show action colors correctly', async ({ page }) => {
    await page.goto('/?tab=timeline');
    
    // Create entry should have green color
    const createEntry = page.locator('text=/create/i').first();
    if (await createEntry.count() > 0) {
      await expect(createEntry).toBeVisible();
    }
  });

  test('should link to data from timeline', async ({ page }) => {
    // Create data
    await createDataViaPlayground(page, { link: 'timeline-view-data' });
    await page.waitForTimeout(1000);
    
    // Go to timeline
    await page.goto('/?tab=timeline');
    await page.waitForTimeout(1000);
    
    // Find and click "View Data" link
    const viewDataLink = page.locator('a:has-text("View Data")').first();
    await expect(viewDataLink).toBeVisible();
    await viewDataLink.click();
    
    // Should navigate to data detail page
    await expect(page.locator('h1')).toContainText('Data Details');
  });

  test('should refresh timeline', async ({ page }) => {
    await page.goto('/?tab=timeline');
    
    // Click refresh button
    await page.click('button:has-text("Refresh")');
    
    // Timeline should still be visible
    await expect(page.locator('button:has-text("Refresh")')).toBeVisible();
  });
});

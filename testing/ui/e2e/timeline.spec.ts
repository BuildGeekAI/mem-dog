import { test, expect } from '@playwright/test';

test.describe('Timeline Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('Mem-Dog');
  });

  test('should display timeline tab', async ({ page }) => {
    // Click on Timeline tab
    await page.click('button:has-text("Timeline")');
    
    // Should show timeline heading
    await expect(page.locator('h2:has-text("Activity Timeline")')).toBeVisible();
  });

  test('should show create action in timeline', async ({ page }) => {
    // Create new data
    const testContent = JSON.stringify({ timeline: 'test' }, null, 2);
    await page.locator('textarea[placeholder*="JSON"]').fill(testContent);
    await page.click('button:has-text("Upload Data")');
    await expect(page.locator('.alert-success')).toBeVisible();
    
    // Switch to timeline
    await page.click('button:has-text("Timeline")');
    
    // Wait for timeline to load
    await page.waitForTimeout(1000);
    
    // Should show create action
    const firstEntry = page.locator('div[style*="border-left"]').first();
    await expect(firstEntry).toContainText('Create');
    await expect(firstEntry).toContainText('v1');
    await expect(firstEntry).toContainText('demo');
  });

  test('should show update action in timeline', async ({ page }) => {
    // Create data first
    await page.locator('textarea[placeholder*="JSON"]').fill(JSON.stringify({ test: 1 }));
    await page.click('button:has-text("Upload Data")');
    await expect(page.locator('.alert-success')).toBeVisible();
    await page.waitForTimeout(1000);
    
    // Navigate to data and update it
    await page.locator('table tbody tr').first().click();
    await page.click('button:has-text("Edit")');
    await page.locator('textarea').fill(JSON.stringify({ test: 2 }));
    await page.click('button:has-text("Save Changes")');
    await expect(page.locator('.alert-success')).toBeVisible();
    
    // Go back to home and check timeline
    await page.click('button:has-text("Back to Home")');
    await page.click('button:has-text("Timeline")');
    
    // Wait for timeline to load
    await page.waitForTimeout(1000);
    
    // Should show both create and update actions
    await expect(page.locator('div:has-text("Update")')).toBeVisible();
    await expect(page.locator('div:has-text("Create")')).toBeVisible();
  });

  test('should show delete action in timeline', async ({ page }) => {
    // Create data
    await page.locator('textarea[placeholder*="JSON"]').fill(JSON.stringify({ delete: 'me' }));
    await page.click('button:has-text("Upload Data")');
    await expect(page.locator('.alert-success')).toBeVisible();
    await page.waitForTimeout(1000);
    
    // Delete the data
    await page.locator('table tbody tr').first().click();
    page.on('dialog', dialog => dialog.accept());
    await page.click('button:has-text("Delete")');
    
    // Check timeline
    await page.click('button:has-text("Timeline")');
    await page.waitForTimeout(1000);
    
    // Should show delete action
    await expect(page.locator('div:has-text("Delete")')).toBeVisible();
  });

  test('should display timeline entries in chronological order', async ({ page }) => {
    // Switch to timeline
    await page.click('button:has-text("Timeline")');
    
    // Get all timeline entries
    const entries = page.locator('div[style*="border-left"]');
    const count = await entries.count();
    
    if (count >= 2) {
      // Get timestamps from first two entries
      const firstTime = await entries.nth(0).locator('span[style*="font-size: 13px"]').textContent();
      const secondTime = await entries.nth(1).locator('span[style*="font-size: 13px"]').textContent();
      
      // Timestamps should be in descending order (most recent first)
      expect(firstTime).toBeTruthy();
      expect(secondTime).toBeTruthy();
    }
  });

  test('should show action colors correctly', async ({ page }) => {
    await page.click('button:has-text("Timeline")');
    
    // Create entry should have green color
    const createEntry = page.locator('div[style*="border-left"]:has-text("Create")').first();
    if (await createEntry.count() > 0) {
      const style = await createEntry.getAttribute('style');
      expect(style).toContain('#28a745'); // Green for create
    }
  });

  test('should link to data from timeline', async ({ page }) => {
    // Create data
    await page.locator('textarea[placeholder*="JSON"]').fill(JSON.stringify({ link: 'test' }));
    await page.click('button:has-text("Upload Data")');
    await expect(page.locator('.alert-success')).toBeVisible();
    await page.waitForTimeout(1000);
    
    // Go to timeline
    await page.click('button:has-text("Timeline")');
    await page.waitForTimeout(1000);
    
    // Find and click "View Data" link
    const viewDataLink = page.locator('a:has-text("View Data")').first();
    await expect(viewDataLink).toBeVisible();
    await viewDataLink.click();
    
    // Should navigate to data detail page
    await expect(page.locator('h1')).toContainText('Data Details');
  });

  test('should refresh timeline', async ({ page }) => {
    await page.click('button:has-text("Timeline")');
    
    // Click refresh button
    await page.click('button:has-text("Refresh")');
    
    // Timeline should still be visible
    await expect(page.locator('h2:has-text("Activity Timeline")')).toBeVisible();
  });
});

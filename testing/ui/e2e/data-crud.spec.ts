import { test, expect } from '@playwright/test';

test.describe('Data CRUD Operations', () => {
  async function goToDataInsert(page: import('@playwright/test').Page) {
    await page.goto('/?tab=testing');
    await page.locator('[data-testid="playground-tab-upload"]').click();
    await expect(page.locator('[data-testid="upload-textarea"]')).toBeVisible();
  }

  async function goToDataList(page: import('@playwright/test').Page) {
    await page.goto('/?tab=data');
    await expect(page.locator('table')).toBeVisible();
  }

  let createdDataId: string;

  test('should create new text data', async ({ page }) => {
    await goToDataInsert(page);
    
    // Fill in text content
    const testContent = JSON.stringify({ 
      test: 'data', 
      timestamp: Date.now() 
    }, null, 2);
    
    await page.locator('[data-testid="upload-textarea"]').fill(testContent);
    
    // Submit form
    await page.click('[data-testid="upload-submit"]');
    
    // Wait for success message
    await expect(page.locator('.alert-success')).toBeVisible();
    await expect(page.locator('.alert-success')).toContainText('uploaded successfully');
    
    // Wait for data to appear in table
    await page.waitForTimeout(1000);
    
    // Verify data appears in list
    await goToDataList(page);
    const firstRow = page.locator('table tbody tr').first();
    await expect(firstRow).toBeVisible();
    
    // Extract data ID from the row
    const dataIdText = await firstRow.locator('td:first-child code').textContent();
    expect(dataIdText).toBeTruthy();
    createdDataId = dataIdText!.replace('...', ''); // Store partial ID
  });

  test('should read and display data', async ({ page }) => {
    await goToDataList(page);
    
    // Click on first data item
    await page.locator('table tbody tr').first().click();
    
    // Wait for data detail page
    await expect(page.locator('h1')).toContainText('Data Details');
    
    // Verify content is displayed
    await expect(page.locator('pre')).toBeVisible();
    
    // Verify version info
    await expect(page.locator('h2')).toContainText('v1');
  });

  test('should update existing data', async ({ page }) => {
    await goToDataList(page);

    // Navigate to first data item
    await page.locator('table tbody tr').first().click();
    await expect(page.locator('h1')).toContainText('Data Details');
    
    // Click Edit button
    await page.click('button:has-text("Edit")');
    
    // Modify content
    const updatedContent = JSON.stringify({ 
      test: 'updated', 
      timestamp: Date.now() 
    }, null, 2);
    
    await page.locator('textarea').fill(updatedContent);
    
    // Save changes
    await page.click('button:has-text("Save Changes")');
    
    // Wait for success message
    await expect(page.locator('.alert-success')).toBeVisible();
    await expect(page.locator('.alert-success')).toContainText('updated successfully');
    
    // Verify version incremented
    await expect(page.locator('h2')).toContainText('v2');
    
    // Verify updated content is displayed
    await expect(page.locator('pre')).toContainText('updated');
  });

  test('should upload file data', async ({ page }) => {
    await goToDataInsert(page);

    // Switch to file upload mode
    await page.click('button:has-text("File Upload")');
    
    // Create a test file
    const fileContent = 'This is a test file content';
    const buffer = Buffer.from(fileContent);
    
    // Upload file
    await page.setInputFiles('input[type="file"]', {
      name: 'test-file.txt',
      mimeType: 'text/plain',
      buffer,
    });
    
    // Submit form
    await page.click('[data-testid="upload-submit"]');
    
    // Wait for success
    await expect(page.locator('.alert-success')).toBeVisible();
  });

  test('should delete data', async ({ page }) => {
    await goToDataList(page);

    // Navigate to last data item (the one we just created)
    await page.locator('table tbody tr').first().click();
    await expect(page.locator('h1')).toContainText('Data Details');
    
    // Set up dialog handler before clicking delete
    page.on('dialog', dialog => dialog.accept());
    
    // Click delete button
    await page.click('button:has-text("Delete")');
    
    // Should redirect to home
    await expect(page.locator('h1')).toContainText('Mem-Dog');
  });
});

---
name: test-automation-engineer
description: Test automation specialist for E2E testing, browser automation, and quality assurance. Use for Selenium MCP integration, Playwright automation, cross-browser testing, Page Object Model, visual regression testing, UAT scenarios, CI/CD test integration, performance testing, and ensuring quality across all 7 Mezzofy portals.
---

# Test Automation Engineer

Build comprehensive automated testing for quality assurance across all portals.

## Tech Stack

- **E2E Testing**: Selenium (MCP), Playwright
- **Unit Testing**: Vitest (frontend), pytest (backend)
- **Visual Regression**: Percy, Chromatic
- **Performance**: Lighthouse, WebPageTest
- **CI/CD**: Jenkins, GitHub Actions
- **Reporting**: Allure, Mochawesome

## Selenium MCP Integration

### Setup

```bash
# Install Selenium MCP server
npm install -g @angiejones/mcp-selenium

# Start Selenium server
npx @angiejones/mcp-selenium start
```

### Using with Claude

```
"Use Selenium MCP to test the coupon redemption flow:
1. Navigate to the B2C portal
2. Search for 'pizza' coupons
3. Select the first coupon
4. Click 'Redeem Now'
5. Verify success message appears"
```

### Python + Selenium

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pytest

class TestCouponRedemption:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup WebDriver before each test"""
        self.driver = webdriver.Chrome()
        self.driver.implicitly_wait(10)
        self.wait = WebDriverWait(self.driver, 10)
        yield
        self.driver.quit()
    
    def test_search_and_redeem_coupon(self):
        """Test complete coupon redemption flow"""
        driver = self.driver
        
        # Navigate to B2C portal
        driver.get('https://mezzofy.com/b2c')
        
        # Login
        self.login('test@example.com', 'password123')
        
        # Search for coupons
        search_input = driver.find_element(By.ID, 'search-input')
        search_input.send_keys('pizza')
        search_input.submit()
        
        # Wait for results
        self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'coupon-card'))
        )
        
        # Click first coupon
        coupon_cards = driver.find_elements(By.CLASS_NAME, 'coupon-card')
        assert len(coupon_cards) > 0, "No coupons found"
        coupon_cards[0].click()
        
        # Click redeem button
        redeem_button = self.wait.until(
            EC.element_to_be_clickable((By.ID, 'redeem-button'))
        )
        redeem_button.click()
        
        # Verify success message
        success_message = self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'success-message'))
        )
        assert 'successfully redeemed' in success_message.text.lower()
    
    def test_expired_coupon_cannot_redeem(self):
        """Test that expired coupons cannot be redeemed"""
        driver = self.driver
        
        # Navigate to specific expired coupon
        driver.get('https://mezzofy.com/b2c/coupon/expired-123')
        
        # Check that redeem button is disabled
        redeem_button = driver.find_element(By.ID, 'redeem-button')
        assert not redeem_button.is_enabled()
        
        # Verify expired indicator
        expired_badge = driver.find_element(By.CLASS_NAME, 'expired-badge')
        assert expired_badge.is_displayed()
        assert 'expired' in expired_badge.text.lower()
    
    def login(self, email: str, password: str):
        """Helper method for login"""
        driver = self.driver
        
        # Click login button
        login_link = driver.find_element(By.LINK_TEXT, 'Login')
        login_link.click()
        
        # Fill credentials
        email_input = self.wait.until(
            EC.presence_of_element_located((By.ID, 'email'))
        )
        email_input.send_keys(email)
        
        password_input = driver.find_element(By.ID, 'password')
        password_input.send_keys(password)
        
        # Submit
        submit_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_button.click()
        
        # Wait for redirect to dashboard
        self.wait.until(EC.url_contains('/dashboard'))
```

## Playwright Automation

### Setup

```bash
npm install -D @playwright/test
npx playwright install
```

### Test Suite

```typescript
// tests/e2e/coupon-redemption.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Coupon Redemption Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('https://mezzofy.com/b2c/login');
    await page.fill('#email', 'test@example.com');
    await page.fill('#password', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');
  });

  test('should successfully redeem a valid coupon', async ({ page }) => {
    // Search for coupons
    await page.goto('https://mezzofy.com/b2c');
    await page.fill('#search-input', 'pizza');
    await page.press('#search-input', 'Enter');
    
    // Wait for results
    await page.waitForSelector('.coupon-card');
    
    // Click first coupon
    await page.click('.coupon-card:first-child');
    
    // Verify coupon details page
    await expect(page.locator('h1')).toContainText('% OFF');
    
    // Click redeem button
    await page.click('#redeem-button');
    
    // Handle biometric mock (in test environment)
    await page.evaluate(() => {
      // Mock biometric authentication
      window.mockBiometricSuccess = true;
    });
    
    // Wait for success message
    await expect(page.locator('.success-message')).toBeVisible();
    await expect(page.locator('.success-message')).toContainText('successfully redeemed');
    
    // Verify coupon status changed
    await page.goto('https://mezzofy.com/b2c/my-coupons');
    const redeemedCoupon = page.locator('.coupon-card').first();
    await expect(redeemedCoupon).toContainText('Redeemed');
  });

  test('should show error for expired coupon', async ({ page }) => {
    // Navigate to expired coupon
    await page.goto('https://mezzofy.com/b2c/coupon/expired-123');
    
    // Verify redeem button is disabled
    const redeemButton = page.locator('#redeem-button');
    await expect(redeemButton).toBeDisabled();
    
    // Verify expired badge
    const expiredBadge = page.locator('.expired-badge');
    await expect(expiredBadge).toBeVisible();
    await expect(expiredBadge).toContainText('Expired');
  });

  test('should enforce usage limits', async ({ page }) => {
    // Navigate to coupon with usage limit reached
    await page.goto('https://mezzofy.com/b2c/coupon/limit-reached-456');
    
    // Try to redeem
    await page.click('#redeem-button');
    
    // Verify error message
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('usage limit');
  });

  test('should work across different browsers', async ({ browserName }) => {
    // This test runs on Chrome, Firefox, and WebKit
    console.log(`Testing on ${browserName}`);
    
    // Test basic flow works on all browsers
    // (Playwright automatically runs this on all configured browsers)
  });
});

// Visual regression test
test('coupon card visual regression', async ({ page }) => {
  await page.goto('https://mezzofy.com/b2c');
  
  const couponCard = page.locator('.coupon-card').first();
  
  // Take screenshot and compare
  await expect(couponCard).toHaveScreenshot('coupon-card.png');
});
```

### Playwright Configuration

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html'],
    ['junit', { outputFile: 'test-results/junit.xml' }],
    ['allure-playwright']
  ],
  use: {
    baseURL: 'https://mezzofy.com',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],
});
```

## Page Object Model

```typescript
// tests/e2e/pages/CouponDetailPage.ts
import { Page, Locator } from '@playwright/test';

export class CouponDetailPage {
  readonly page: Page;
  readonly title: Locator;
  readonly discountBadge: Locator;
  readonly merchantLogo: Locator;
  readonly description: Locator;
  readonly expirationDate: Locator;
  readonly redeemButton: Locator;
  readonly saveButton: Locator;
  readonly shareButton: Locator;
  readonly successMessage: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.title = page.locator('h1.coupon-title');
    this.discountBadge = page.locator('.discount-badge');
    this.merchantLogo = page.locator('.merchant-logo');
    this.description = page.locator('.coupon-description');
    this.expirationDate = page.locator('.expiration-date');
    this.redeemButton = page.locator('#redeem-button');
    this.saveButton = page.locator('#save-button');
    this.shareButton = page.locator('#share-button');
    this.successMessage = page.locator('.success-message');
    this.errorMessage = page.locator('.error-message');
  }

  async goto(couponId: string) {
    await this.page.goto(`/b2c/coupon/${couponId}`);
  }

  async redeem() {
    await this.redeemButton.click();
  }

  async save() {
    await this.saveButton.click();
  }

  async share() {
    await this.shareButton.click();
  }

  async getDiscountAmount(): Promise<string> {
    return await this.discountBadge.textContent() || '';
  }

  async isRedeemButtonEnabled(): Promise<boolean> {
    return await this.redeemButton.isEnabled();
  }

  async waitForSuccess() {
    await this.successMessage.waitFor({ state: 'visible' });
  }

  async waitForError() {
    await this.errorMessage.waitFor({ state: 'visible' });
  }
}

// Usage in test
import { CouponDetailPage } from './pages/CouponDetailPage';

test('redeem coupon using page object', async ({ page }) => {
  const couponPage = new CouponDetailPage(page);
  
  await couponPage.goto('active-123');
  await couponPage.redeem();
  await couponPage.waitForSuccess();
  
  expect(await couponPage.isRedeemButtonEnabled()).toBe(false);
});
```

## API Testing

```typescript
// tests/api/coupon-api.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Coupon API', () => {
  let authToken: string;

  test.beforeAll(async ({ request }) => {
    // Login to get auth token
    const response = await request.post('/api/v2/auth/login', {
      data: {
        email: 'test@example.com',
        password: 'password123'
      }
    });
    
    const data = await response.json();
    authToken = data.accessToken;
  });

  test('GET /coupons should return list', async ({ request }) => {
    const response = await request.get('/api/v2/coupons', {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      params: {
        status: 'active',
        limit: 10
      }
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.data).toBeInstanceOf(Array);
    expect(data.pagination.limit).toBe(10);
  });

  test('POST /coupons should create new coupon', async ({ request }) => {
    const response = await request.post('/api/v2/coupons', {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        title: 'Test Coupon',
        discount: 50,
        discountType: 'percentage',
        merchantId: '7c9e6679-7425-40de-944b-e07fc1f90ae7',
        expiresAt: '2025-12-31T23:59:59Z'
      }
    });

    expect(response.status()).toBe(201);
    
    const data = await response.json();
    expect(data.id).toBeDefined();
    expect(data.title).toBe('Test Coupon');
  });

  test('POST /coupons/:id/redeem should redeem coupon', async ({ request }) => {
    const response = await request.post('/api/v2/coupons/active-123/redeem', {
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.redemptionId).toBeDefined();
  });

  test('should handle validation errors', async ({ request }) => {
    const response = await request.post('/api/v2/coupons', {
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      data: {
        title: 'A',  // Too short
        discount: 150,  // Too high
        discountType: 'invalid'
      }
    });

    expect(response.status()).toBe(400);
    
    const data = await response.json();
    expect(data.error).toBe('ValidationError');
  });
});
```

## Performance Testing

```typescript
// tests/performance/lighthouse.spec.ts
import { test } from '@playwright/test';
import { playAudit } from 'playwright-lighthouse';

test('homepage performance audit', async ({ page }) => {
  await page.goto('https://mezzofy.com/b2c');
  
  await playAudit({
    page,
    thresholds: {
      performance: 90,
      accessibility: 90,
      'best-practices': 85,
      seo: 85,
    },
    port: 9222,
  });
});

// tests/performance/load-test.ts
import { test } from '@playwright/test';

test('load test - 100 concurrent users', async ({ page }) => {
  const promises = [];
  
  for (let i = 0; i < 100; i++) {
    promises.push(
      page.goto('https://mezzofy.com/b2c')
        .then(() => page.waitForLoadState('networkidle'))
    );
  }
  
  const start = Date.now();
  await Promise.all(promises);
  const duration = Date.now() - start;
  
  console.log(`100 requests completed in ${duration}ms`);
  
  // Assert acceptable performance
  expect(duration).toBeLessThan(5000); // 5 seconds
});
```

## Visual Regression Testing

```typescript
// tests/visual/coupon-card.spec.ts
import { test, expect } from '@playwright/test';

test('coupon card visual regression', async ({ page }) => {
  await page.goto('https://mezzofy.com/b2c');
  
  // Wait for coupon cards to load
  await page.waitForSelector('.coupon-card');
  
  // Take screenshot of first coupon card
  const couponCard = page.locator('.coupon-card').first();
  await expect(couponCard).toHaveScreenshot('coupon-card.png', {
    maxDiffPixels: 100,
  });
});

test('responsive design - mobile', async ({ page }) => {
  // Set mobile viewport
  await page.setViewportSize({ width: 375, height: 667 });
  
  await page.goto('https://mezzofy.com/b2c');
  
  // Screenshot entire page
  await expect(page).toHaveScreenshot('homepage-mobile.png', {
    fullPage: true,
  });
});

test('responsive design - tablet', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  
  await page.goto('https://mezzofy.com/b2c');
  
  await expect(page).toHaveScreenshot('homepage-tablet.png', {
    fullPage: true,
  });
});
```

## CI/CD Integration

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        browser: [chromium, firefox, webkit]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Install Playwright browsers
        run: npx playwright install --with-deps ${{ matrix.browser }}
      
      - name: Run E2E tests
        run: npx playwright test --project=${{ matrix.browser }}
        env:
          TEST_EMAIL: ${{ secrets.TEST_EMAIL }}
          TEST_PASSWORD: ${{ secrets.TEST_PASSWORD }}
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report-${{ matrix.browser }}
          path: playwright-report/
      
      - name: Upload screenshots
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: screenshots-${{ matrix.browser }}
          path: test-results/
```

## Test Data Management

```typescript
// tests/fixtures/coupon-data.ts
export const testCoupons = {
  valid: {
    id: 'active-123',
    title: '50% Off Pizza',
    discount: 50,
    discountType: 'percentage',
    status: 'active',
    expiresAt: '2025-12-31T23:59:59Z',
  },
  expired: {
    id: 'expired-123',
    title: 'Expired Deal',
    discount: 30,
    discountType: 'percentage',
    status: 'expired',
    expiresAt: '2024-01-01T00:00:00Z',
  },
  limitReached: {
    id: 'limit-reached-456',
    title: 'Limited Offer',
    discount: 75,
    discountType: 'percentage',
    status: 'active',
    maxUses: 100,
    currentUses: 100,
  },
};

// tests/helpers/test-helpers.ts
export async function createTestCoupon(overrides = {}) {
  const coupon = {
    title: 'Test Coupon',
    discount: 50,
    discountType: 'percentage',
    merchantId: '7c9e6679-7425-40de-944b-e07fc1f90ae7',
    expiresAt: '2025-12-31T23:59:59Z',
    ...overrides,
  };
  
  const response = await apiClient.post('/coupons', coupon);
  return response.data;
}

export async function cleanupTestData(couponIds: string[]) {
  for (const id of couponIds) {
    await apiClient.delete(`/coupons/${id}`);
  }
}
```

## Test Reporting

```bash
# Generate Allure report
npx allure generate ./allure-results --clean
npx allure open

# Playwright HTML report
npx playwright show-report

# Coverage report
npx playwright test --coverage
```

## Quality Checklist

- [ ] E2E tests cover critical user journeys
- [ ] API tests for all endpoints
- [ ] Cross-browser testing (Chrome, Firefox, Safari)
- [ ] Mobile responsive testing
- [ ] Visual regression tests
- [ ] Performance benchmarks
- [ ] Accessibility tests (WCAG 2.1 AA)
- [ ] Load testing completed
- [ ] Test data cleanup automated
- [ ] CI/CD integration working
- [ ] Test reports generated
- [ ] Flaky tests identified and fixed
- [ ] Test coverage > 80%
- [ ] Page Object Model implemented
- [ ] Error scenarios tested

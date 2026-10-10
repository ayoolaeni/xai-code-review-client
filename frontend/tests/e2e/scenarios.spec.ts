import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  enterCode,
  login,
  register,
  sample,
  SAMPLES,
  waitForReport,
} from "./helpers";

test.describe.configure({ mode: "serial" });

test("1. guest analyses the SQL-injection sample end to end", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Privacy:/)).toBeVisible();
  await enterCode(page, sample("p01_user_lookup.py"), "p01_user_lookup.py");
  await page.getByTestId("analyse-button").click();

  await page.waitForURL(/\/report\//);
  await waitForReport(page);
  await expect(page.getByText("Overall risk").locator("..")).toContainText("Critical");

  // Open the critical finding.
  await page.getByRole("tab", { name: /Risks/ }).click();
  const card = page.getByTestId("finding-card").first();
  await card.getByRole("button", { expanded: false }).first().click();
  await expect(card.getByText("Why it matters")).toBeVisible();
  await expect(card).toContainText("Severity: Critical");
  await expect(card).toContainText("Found by:");

  // Improved code (the gate opens after reading the critical finding).
  await page.getByRole("tab", { name: "Improved Code" }).click();
  await expect(page.getByText("You reviewed the critical findings.")).toBeVisible();
  await expect(page.getByTestId("diff-editor")).toBeVisible();

  // PDF download (E2E_NO_PDF=1 when the server has no PDF library, e.g. a Windows dev server).
  if (process.env.E2E_NO_PDF) {
    await page.getByRole("button", { name: /Download PDF/ }).click();
    await expect(page.getByText(/PDF export is not available on this server/)).toBeVisible();
  } else {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: /Download PDF/ }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/^xai-report-.{8}\.pdf$/);
  }

  // Rate the explanation.
  await page.locator("label", { hasText: "4 stars" }).click();
  await expect(page.getByRole("radio", { name: "4 stars" })).toBeChecked();
  await page.getByLabel("Yes").check();
  await page.getByRole("button", { name: "Submit rating" }).click();
  await expect(page.getByText("Thank you for your feedback")).toBeVisible();
});

test("2. uploading a .java file sets the language automatically", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("file-input").setInputFiles(`${SAMPLES}/V01UserDao.java`);
  await expect(page.getByLabel("Language")).toHaveValue("java");
  await expect(page.getByText("Loaded: V01UserDao.java")).toBeVisible();
  await page.getByTestId("analyse-button").click();
  await waitForReport(page);
  await expect(page.getByText(/Java/).first()).toBeVisible();
});

test("3. 401 lines are rejected without navigation", async ({ page }) => {
  await page.goto("/");
  const code = Array.from({ length: 401 }, (_, i) => `x${i} = ${i}`).join("\n");
  await page
    .getByTestId("file-input")
    .setInputFiles({ name: "long.py", mimeType: "text/plain", buffer: Buffer.from(code) });
  await expect(page.getByTestId("line-counter")).toContainText("Lines: 401 / 400");
  await expect(page.getByTestId("line-counter")).toContainText("too long");
  await expect(page.getByTestId("analyse-button")).toBeDisabled();
  await expect(page).toHaveURL("/");
});

test("4. registered user: no stored code, history, reopen, delete", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  await register(page, email);
  await page.goto("/");
  await expect(page.getByLabel("Keep my code in my history")).not.toBeChecked();
  await page.getByTestId("file-input").setInputFiles(`${SAMPLES}/p06_password_store.py`);
  await page.getByTestId("analyse-button").click();
  await waitForReport(page);
  const reportUrl = page.url();
  await page.getByRole("tab", { name: "Transparency" }).click();
  await expect(page.getByText(/original code was not stored/)).toBeVisible();

  await page.goto("/history");
  const row = page.getByRole("row", { name: /p06_password_store\.py/ });
  await expect(row).toBeVisible();
  await row.getByRole("link").click();
  await expect(page).toHaveURL(reportUrl.replace(/#.*$/, ""));
  await page.goto("/history");
  await page
    .getByRole("button", { name: /Delete the analysis/ })
    .first()
    .click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("You have no analyses yet.")).toBeVisible();
});

test("5. admin lowers max_lines, a 60-line submission is rejected, then resets", async ({ page }) => {
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.goto("/admin/settings");
  await page.getByLabel("Maximum lines per submission").fill("50");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText(/Settings saved/)).toBeVisible();

  await page.goto("/");
  const code = Array.from({ length: 60 }, (_, i) => `y${i} = ${i}`).join("\n");
  await page
    .getByTestId("file-input")
    .setInputFiles({ name: "sixty.py", mimeType: "text/plain", buffer: Buffer.from(code) });
  await expect(page.getByTestId("line-counter")).toContainText("Lines: 60 / 50");
  await expect(page.getByTestId("analyse-button")).toBeDisabled();

  await page.goto("/admin/settings");
  const card = page.locator(".card", { has: page.getByLabel("Maximum lines per submission") });
  await card.getByRole("button", { name: "Reset to default" }).click();
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText(/Settings saved/)).toBeVisible();
  await page.goto("/admin/stats");
  await expect(page.getByText("AI usage today (Gemini free tier)")).toBeVisible();
});

test("6. accessibility: no serious or critical axe violations", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("code-editor").locator(".monaco-editor").waitFor();
  const home = await new AxeBuilder({ page }).exclude(".monaco-editor").analyze();
  expect(home.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);

  await page.getByTestId("file-input").setInputFiles(`${SAMPLES}/j01_comment_widget.js`);
  await page.getByTestId("analyse-button").click();
  await waitForReport(page);
  const report = await new AxeBuilder({ page }).exclude(".monaco-editor").analyze();
  expect(report.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);
});

import { expect, test } from "@playwright/test";
import { readdirSync } from "node:fs";

import { SAMPLES, waitForReport } from "./helpers";

// Acceptance (Section 21 / M7): every benchmark sample gives a complete report with all five tabs
// and no console errors. Run with: npx playwright test all-samples --project=chromium-desktop
const files = readdirSync(SAMPLES).sort();

for (const file of files) {
  test(`complete report for ${file}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() !== "error") return;
      // A guest's session check gets the 401 the API contract specifies (7.2); the browser logs it as a
      // network error although the app handles it. Any other console error still fails the test.
      const guestSessionCheck =
        msg.text().startsWith("Failed to load resource") && msg.location().url.endsWith("/api/auth/me");
      if (!guestSessionCheck) errors.push(msg.text());
    });
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/");
    await page.getByTestId("file-input").setInputFiles(`${SAMPLES}/${file}`);
    await page.getByTestId("analyse-button").click();
    await waitForReport(page);
    for (const name of ["Overview", "Breakdown", /Risks/, "Improved Code", "Transparency"]) {
      await page.getByRole("tab", { name }).click();
      await expect(page.getByRole("tabpanel")).toBeVisible();
    }
    expect(errors).toEqual([]);
  });
}

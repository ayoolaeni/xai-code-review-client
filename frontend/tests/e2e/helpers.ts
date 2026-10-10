import { expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const SAMPLES = path.resolve(here, "../../../evaluation/benchmark/samples");

export const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";

export function sample(name: string): string {
  return readFileSync(path.join(SAMPLES, name), "utf-8");
}

/** Put code into the Monaco editor. Uses the clipboard where allowed (a real paste), otherwise a file upload. */
export async function enterCode(page: Page, code: string, filename = "snippet.py") {
  const editor = page.getByTestId("code-editor");
  await editor.locator(".monaco-editor").waitFor();
  const pasted = await page
    .evaluate(async (text) => {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        return false;
      }
    }, code)
    .catch(() => false);
  if (pasted) {
    await editor.locator(".monaco-editor").click();
    await page.keyboard.press(process.platform === "darwin" ? "Meta+V" : "Control+V");
  } else {
    await page
      .getByTestId("file-input")
      .setInputFiles({ name: filename, mimeType: "text/plain", buffer: Buffer.from(code) });
  }
  const lines = code.replace(/\s+$/, "").split("\n").length;
  await expect(page.getByTestId("line-counter")).toContainText(`Lines: ${lines} /`);
}

export async function waitForReport(page: Page) {
  await page.waitForURL(/\/report\//);
  await expect(page.getByRole("heading", { name: "Code review report" })).toBeVisible({ timeout: 90_000 });
}

export async function register(page: Page, email: string, password = "Password123") {
  await page.goto("/register");
  await page.getByLabel("Full name").fill("E2E User");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Register" }).click();
  await page.waitForURL("/");
}

export async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL("/");
}

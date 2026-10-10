import { request, type FullConfig } from "@playwright/test";

import { ADMIN_EMAIL, ADMIN_PASSWORD } from "./helpers";

const RAISED = { guest_rate_limit_per_hour: 1000, user_rate_limit_per_hour: 1000, max_lines: 400 };

/** The e2e suite runs dozens of analyses from one IP: raise the hourly limits through the admin API. */
export async function adminSettings(config: FullConfig, body: Record<string, unknown>) {
  const baseURL = config.projects[0].use.baseURL as string;
  const ctx = await request.newContext({ baseURL, extraHTTPHeaders: { Origin: baseURL } });
  const login = await ctx.post("/api/auth/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } });
  if (!login.ok()) {
    throw new Error(
      `E2E setup could not log in as ${ADMIN_EMAIL} (${login.status()}). Set E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD.`,
    );
  }
  const res = await ctx.put("/api/admin/settings", { data: body });
  if (!res.ok()) throw new Error(`E2E setup could not update settings: ${res.status()} ${await res.text()}`);
  await ctx.dispose();
}

export default async function globalSetup(config: FullConfig) {
  await adminSettings(config, RAISED);
}

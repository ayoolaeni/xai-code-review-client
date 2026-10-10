import type { FullConfig } from "@playwright/test";

import { adminSettings } from "./global-setup";

/** Restore the default limits after the e2e run. */
export default async function globalTeardown(config: FullConfig) {
  await adminSettings(config, { guest_rate_limit_per_hour: 10, user_rate_limit_per_hour: 30, max_lines: 400 });
}

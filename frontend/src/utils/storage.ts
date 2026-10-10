// Browser storage can throw (private mode, blocked cookies), so every access is guarded.

function safeGet(storage: () => Storage, key: string): string | null {
  try {
    return storage().getItem(key);
  } catch {
    return null;
  }
}

function safeSet(storage: () => Storage, key: string, value: string): void {
  try {
    storage().setItem(key, value);
  } catch {
    /* storage unavailable — ignore */
  }
}

const local = () => window.localStorage;
const session = () => window.sessionStorage;

export function getFeedbackToken(publicId: string): string | null {
  return safeGet(local, `xai-feedback-${publicId}`);
}

export function setFeedbackToken(publicId: string, token: string): void {
  safeSet(local, `xai-feedback-${publicId}`, token);
}

/** CRITICAL findings opened in this browser session (cognitive-forcing gate, Section 11.5). */
export function getOpenedFindings(publicId: string): string[] {
  const raw = safeGet(session, `xai-opened-${publicId}`);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function setOpenedFindings(publicId: string, keys: string[]): void {
  safeSet(session, `xai-opened-${publicId}`, JSON.stringify(keys));
}

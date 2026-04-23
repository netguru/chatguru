const VISITOR_ID_STORAGE_KEY = "chatguru.visitor_id";

function generateVisitorId(): string {
  return crypto.randomUUID();
}

export function getOrCreateVisitorId(): string {
  const generated = generateVisitorId();

  try {
    const existing = window.localStorage.getItem(VISITOR_ID_STORAGE_KEY);
    if (existing && existing.trim().length > 0) {
      return existing;
    }

    window.localStorage.setItem(VISITOR_ID_STORAGE_KEY, generated);
  } catch {
    return generated;
  }

  return generated;
}

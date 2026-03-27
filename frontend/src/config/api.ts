function normalizeApiBase(input: string): string {
  const trimmed = (input || "").trim().replace(/\/+$/, "")
  if (!trimmed) return "/api/v1"
  if (trimmed.endsWith("/api/v1")) return trimmed
  return `${trimmed}/api/v1`
}

function resolveConfiguredApiUrl(): string {
  const configured = String(import.meta.env.VITE_API_URL || "").trim()
  if (!configured) return ""

  try {
    const resolved = new URL(configured, window.location.origin)
    if (window.location.protocol === "https:" && resolved.protocol === "http:") {
      resolved.protocol = "https:"
    }
    return resolved.toString().replace(/\/+$/, "")
  } catch {
    return configured.replace(/\/+$/, "")
  }
}

export function getApiBase(): string {
  const configured = resolveConfiguredApiUrl()
  if (!configured) return "/api/v1"

  const useSameOriginProxy = String(import.meta.env.VITE_USE_SAME_ORIGIN_PROXY || "true")
    .toLowerCase()
    .trim() !== "false"

  // In production, prefer same-origin /api rewrites to avoid CORS and mixed-content issues.
  if (import.meta.env.PROD && useSameOriginProxy) {
    return "/api/v1"
  }

  return normalizeApiBase(configured)
}

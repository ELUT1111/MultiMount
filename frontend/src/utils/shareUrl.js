export function currentPublicOrigin() {
  if (typeof window === 'undefined') return ''
  return `${window.location.protocol}//${window.location.host}`
}

export function buildShareUrl(token) {
  return `${currentPublicOrigin()}/share/${encodeURIComponent(token)}`
}

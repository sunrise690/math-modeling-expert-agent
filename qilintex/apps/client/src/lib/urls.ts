export function sessionFromHash(hash: string) {
  return new URLSearchParams(hash.replace(/^#/, '')).get('session') || ''
}

export function realmFromHash(hash: string) {
  return new URLSearchParams(hash.replace(/^#/, '')).get('realm') === 'oauth' ? 'oauth' as const : 'team' as const
}

export function invitationFromSearch(search: string) {
  return new URLSearchParams(search).get('invite') || ''
}

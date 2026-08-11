export function parseDeepLink(args) {
  const value = args.find((arg) => arg.startsWith('tonggaotex://'))
  if (!value) return null
  try {
    const url = new URL(value)
    const ticket = url.searchParams.get('ticket')
    return ticket ? { type: 'auth', ticket } : null
  } catch {
    return null
  }
}

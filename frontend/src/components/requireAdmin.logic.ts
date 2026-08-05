/** Pure decision for the admin route guard. Kept separate from the component
 *  so it can be unit-tested without a DOM (the frontend test env is node-only). */
export type AdminGuardState = 'loading' | 'redirect' | 'allow'

export function adminGuardState(user: { role?: string } | null | undefined): AdminGuardState {
  if (user === undefined) return 'loading'
  if (!user || user.role !== 'admin') return 'redirect'
  return 'allow'
}

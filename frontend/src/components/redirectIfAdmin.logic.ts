/** True when an admin should be bounced off a normal-user page to the console. */
export function shouldRedirectAdmin(user: { role?: string } | null | undefined): boolean {
  return user?.role === 'admin'
}

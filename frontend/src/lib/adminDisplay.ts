/** 管理后台用户展示名：有用户名用用户名，否则占位。user_id 作小字副显在页面另行渲染。 */
export function displayName(username: string | null | undefined): string {
  return username && username.trim() ? username : '(已删除/未知)'
}

import { useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { PanelLeft } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { logout } from '@/api/auth'
import { useAuth } from '@/hooks/useAuth'
import { useMembership } from '@/hooks/useMembership'
import { queryClient } from '@/lib/queryClient'
import { ADMIN_GROUPS, NAV_GROUPS } from '@/lib/nav'
import { PATHS } from '@/lib/paths'
import { cn } from '@/lib/utils'

/**
 * 左侧可折叠导航（handoff 第 3 屏）：展开 232px / 收起 66px，粘顶全高，
 * 右侧 1px 细线。当前项 = accent-wash 底 + 赤陶字；收起时组标签变细线。
 * 导航数据在 lib/nav.ts(四组十三项);历史试卷/会员/设置/登出收进底部
 * 头像个人菜单(向上弹出,collapsed 时从头像旁弹出)。
 * 管理员登录时主导航替换为管理后台菜单（不显示普通功能）。
 */
export function Sidebar() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('sidebarCollapsed') === '1',
  )
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const { data: user } = useAuth()
  const { isMember, expiresAt } = useMembership()
  const navigate = useNavigate()

  const isAdmin = user?.role === 'admin'
  const groups = isAdmin ? ADMIN_GROUPS : NAV_GROUPS

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      navigate(PATHS.login)
    },
  })

  const toggle = () => {
    setCollapsed((v) => {
      localStorage.setItem('sidebarCollapsed', v ? '0' : '1')
      return !v
    })
  }

  // 点击菜单外 / Escape 关闭（原生 dropdown 未引入,手写失焦逻辑）
  useEffect(() => {
    if (!menuOpen) return
    const onPointerDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

  const memberPill = isMember && (
    <span
      className="shrink-0 rounded-sm border border-accent/40 px-1 py-px font-ui text-[10px] leading-none text-accent"
      title={expiresAt ? `会员有效期至 ${expiresAt.slice(0, 10)}` : undefined}
    >
      会员
    </span>
  )

  const menuItemClass =
    'flex items-center px-3 py-2 font-ui text-[14px] text-muted-ink transition-colors hover:bg-tint hover:text-ink'

  return (
    <aside
      className="sticky top-0 flex h-svh shrink-0 flex-col border-r border-hairline transition-[width] duration-250 ease-out print:hidden"
      style={{ width: collapsed ? 66 : 232 }}
    >
      {/* 顶部 64px：品牌（回营销首页） + 折叠按钮 */}
      <div
        className={cn(
          'flex h-16 shrink-0 items-center px-3.5',
          collapsed ? 'justify-center' : 'justify-between',
        )}
      >
        {!collapsed && (
          <NavLink
            to={PATHS.home}
            className="whitespace-nowrap text-[17px] tracking-[0.06em] text-ink [font-family:var(--font-display)]"
          >
            试卷生成器
          </NavLink>
        )}
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? '展开导航' : '收起导航'}
          className="flex size-[30px] items-center justify-center rounded-sm text-muted-ink transition-colors hover:bg-tint hover:text-accent"
        >
          <PanelLeft className="size-[18px]" strokeWidth={1.5} />
        </button>
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-3.5 pb-4">
        {groups.map((group) => (
          <div key={group.label} className="flex flex-col gap-0.5">
            {collapsed ? (
              <div aria-hidden className="mx-1 my-2.5 border-t border-hairline" />
            ) : (
              <div className="px-3 pb-1 pt-4 font-ui text-[10.5px] font-bold tracking-[0.14em] text-quiet">
                {group.label}
              </div>
            )}
            {group.items.map(({ to, label, icon: Icon, end, disabled, badge }) =>
              disabled ? (
                // 未上线入口：不可点占位（不用赤陶——不可交互处不给强调色）
                <span
                  key={to}
                  title={collapsed ? label : undefined}
                  className={cn(
                    'flex cursor-default items-center gap-3 rounded-sm px-3 py-[9px] font-ui text-[14.5px] text-quiet',
                    collapsed && 'justify-center px-0',
                  )}
                >
                  <Icon className="size-[18px] shrink-0" strokeWidth={1.5} />
                  {!collapsed && (
                    <span className="flex items-center gap-1.5 whitespace-nowrap">
                      {label}
                      {badge && (
                        <span className="rounded-sm border border-hairline px-1 py-px font-ui text-[10px] leading-none">
                          {badge}
                        </span>
                      )}
                    </span>
                  )}
                </span>
              ) : (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  title={collapsed ? label : undefined}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-sm px-3 py-[9px] font-ui text-[14.5px] transition-colors',
                      collapsed && 'justify-center px-0',
                      isActive
                        ? 'bg-wash text-accent'
                        : 'text-muted-ink hover:bg-tint hover:text-ink',
                    )
                  }
                >
                  <Icon className="size-[18px] shrink-0" strokeWidth={1.5} />
                  {!collapsed && <span className="whitespace-nowrap">{label}</span>}
                </NavLink>
              ),
            )}
          </div>
        ))}
      </nav>

      {/* 底部用户区：点击弹出个人菜单（历史试卷/会员/设置/登出） */}
      <div
        ref={menuRef}
        className={cn(
          'relative shrink-0 border-t border-hairline px-2 py-2',
          collapsed && 'flex justify-center px-0',
        )}
      >
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          title={collapsed ? (user?.username ?? '个人菜单') : undefined}
          onClick={() => setMenuOpen((v) => !v)}
          className={cn(
            'flex items-center gap-2.5 rounded-sm px-1.5 py-1.5 text-left transition-colors hover:bg-tint',
            collapsed ? 'justify-center' : 'w-full',
          )}
        >
          <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-tint font-ui text-[13px] text-muted-ink">
            {(user?.username ?? '?').slice(0, 1).toUpperCase()}
          </span>
          {!collapsed && (
            <span className="flex min-w-0 items-center gap-1.5">
              <span className="truncate font-ui text-[14px] text-ink">{user?.username}</span>
              {memberPill}
            </span>
          )}
        </button>

        {menuOpen && (
          <div
            role="menu"
            className={cn(
              'absolute z-40 flex flex-col rounded-md border border-hairline bg-paper py-1.5',
              collapsed ? 'bottom-2 left-full ml-2 w-44' : 'bottom-full left-2 right-2 mb-1.5',
            )}
            style={{ boxShadow: 'var(--shadow-overlay)' }}
          >
            {/* 用户名行（只读） */}
            <div className="flex items-center gap-1.5 px-3 py-2">
              <span className="truncate font-ui text-[14px] text-ink">{user?.username}</span>
              {memberPill}
            </div>
            <div aria-hidden className="my-1 border-t border-hairline" />
            <NavLink
              to={PATHS.papers}
              role="menuitem"
              className={menuItemClass}
              onClick={() => setMenuOpen(false)}
            >
              历史试卷
            </NavLink>
            <NavLink
              to={PATHS.membership}
              role="menuitem"
              className={menuItemClass}
              onClick={() => setMenuOpen(false)}
            >
              会员
            </NavLink>
            {!isAdmin && (
              <NavLink
                to={PATHS.settings}
                role="menuitem"
                className={menuItemClass}
                onClick={() => setMenuOpen(false)}
              >
                设置
              </NavLink>
            )}
            <div aria-hidden className="my-1 border-t border-hairline" />
            <button
              type="button"
              role="menuitem"
              disabled={logoutMutation.isPending}
              className={cn(menuItemClass, 'disabled:pointer-events-none disabled:opacity-60')}
              onClick={() => {
                setMenuOpen(false)
                logoutMutation.mutate()
              }}
            >
              登出
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}

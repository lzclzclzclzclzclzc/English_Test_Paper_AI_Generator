import { useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { PanelLeft } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { logout } from '@/api/auth'
import { useAuth } from '@/hooks/useAuth'
import { useCredits } from '@/hooks/useCredits'
import { queryClient } from '@/lib/queryClient'
import { ADMIN_GROUPS, NAV_GROUPS } from '@/lib/nav'
import { PATHS } from '@/lib/paths'
import { cn } from '@/lib/utils'

/**
 * 左侧可折叠导航（handoff 第 3 屏）：展开 232px / 收起 66px，粘顶全高，
 * 右侧 1px 细线。当前项 = 深底 + 橙红左线；收起时组标签变细线。
 * 导航数据在 lib/nav.ts（两个顶级项 主页/学习助手 + 四组 练习/出卷/背词/复盘）；
 * 积分/设置/登出收进底部头像个人菜单(向上弹出,collapsed 时从头像旁弹出)。
 * 管理员登录时主导航替换为管理后台菜单（不显示普通功能）。
 */
export function Sidebar() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('sidebarCollapsed') === '1',
  )
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const { data: user } = useAuth()
  const { total: creditsTotal } = useCredits()
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

  // 积分小标：用户名旁的余额（深色侧栏里用 sb-badge 细边样式）
  const creditsBadge = creditsTotal !== null && (
    <span className="sb-badge shrink-0 tabular-nums" title="当前可用积分">
      {creditsTotal} 积分
    </span>
  )

  const menuItemClass = 'sb-menu-item'

  return (
    <aside
      className="sidebar-swiss sticky top-0 flex h-svh shrink-0 flex-col transition-[width] duration-250 ease-out print:hidden"
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
          <NavLink to={PATHS.home} className="sb-brand">
            <span className="sb-mark">卷</span>
            <span>卷王</span>
          </NavLink>
        )}
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? '展开导航' : '收起导航'}
          className="sb-toggle"
        >
          <PanelLeft className="size-[18px]" strokeWidth={1.5} />
        </button>
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-3.5 pb-4">
        {groups.map((group, groupIndex) => (
          <div key={group.label || `top-${groupIndex}`} className="flex flex-col gap-0.5">
            {group.label &&
              (collapsed ? (
                <div aria-hidden className="sb-divider" />
              ) : (
                <div className="sb-group">
                  {group.label}
                </div>
              ))}
            {group.items.map(({ to, label, icon: Icon, end, disabled, badge }) =>
              disabled ? (
                // 未上线入口：不可点占位
                <span
                  key={to}
                  title={collapsed ? label : undefined}
                  className={cn('sb-item is-disabled', collapsed && 'justify-center px-0')}
                >
                  <Icon className="size-[18px] shrink-0" strokeWidth={1.5} />
                  {!collapsed && (
                    <span className="flex items-center gap-1.5 whitespace-nowrap">
                      {label}
                      {badge && <span className="sb-badge">{badge}</span>}
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
                    cn('sb-item', collapsed && 'justify-center px-0', isActive && 'is-active')
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

      {/* 底部用户区：点击弹出个人菜单（积分/设置/登出） */}
      <div
        ref={menuRef}
        className={cn('sb-user-area', collapsed && 'flex justify-center px-0')}
      >
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          title={collapsed ? (user?.username ?? '个人菜单') : undefined}
          onClick={() => setMenuOpen((v) => !v)}
          className={cn('sb-user-btn', collapsed ? 'justify-center' : 'w-full')}
        >
          <span className="sb-avatar">
            {(user?.username ?? '?').slice(0, 1).toUpperCase()}
          </span>
          {!collapsed && (
            <span className="flex min-w-0 items-center gap-1.5">
              <span className="truncate font-ui text-[14px]">{user?.username}</span>
              {creditsBadge}
            </span>
          )}
        </button>

        {menuOpen && (
          <div
            role="menu"
            className={cn(
              'sb-menu',
              collapsed ? 'bottom-2 left-full ml-2 w-44' : 'bottom-full left-2 right-2 mb-1.5',
            )}
          >
            {/* 用户名行（只读） */}
            <div className="flex items-center gap-1.5 px-3 py-2">
              <span className="truncate font-ui text-[14px]">{user?.username}</span>
              {creditsBadge}
            </div>
            <div aria-hidden className="sb-menu-divider" />
            <NavLink to={PATHS.credits} role="menuitem" className={menuItemClass} onClick={() => setMenuOpen(false)}>
              积分与充值
            </NavLink>
            {!isAdmin && (
              <NavLink to={PATHS.settings} role="menuitem" className={menuItemClass} onClick={() => setMenuOpen(false)}>
                设置
              </NavLink>
            )}
            <div aria-hidden className="sb-menu-divider" />
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

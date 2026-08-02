import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  BadgeCheck,
  BarChart3,
  CalendarCheck,
  LayoutDashboard,
  List,
  MessageCircle,
  PanelLeft,
  Pen,
  ScrollText,
  Settings,
  Users,
  XCircle,
} from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { logout } from '@/api/auth'
import { useAuth } from '@/hooks/useAuth'
import { useMembership } from '@/hooks/useMembership'
import { queryClient } from '@/lib/queryClient'
import { cn } from '@/lib/utils'

const GROUPS = [
  {
    label: '出卷',
    items: [
      { to: '/', label: '生成试卷', icon: Pen, end: true },
      { to: '/assistant', label: '学习助手', icon: MessageCircle, end: true },
      { to: '/papers', label: '历史试卷', icon: List, end: false },
    ],
  },
  {
    label: '复习',
    items: [
      { to: '/review', label: '错题本', icon: XCircle, end: true },
      { to: '/mastery', label: '掌握度', icon: BarChart3, end: true },
      { to: '/study-plan', label: '学习计划', icon: CalendarCheck, end: true },
    ],
  },
  {
    label: '资料',
    items: [
      { to: '/membership', label: '会员', icon: BadgeCheck, end: true },
      { to: '/settings', label: '设置', icon: Settings, end: true },
    ],
  },
] as const

const ADMIN_GROUPS = [
  {
    label: '管理后台',
    items: [
      { to: '/admin', label: '概览', icon: LayoutDashboard, end: true },
      { to: '/admin/users', label: '用户', icon: Users, end: false },
      { to: '/admin/memberships', label: '会员', icon: BadgeCheck, end: true },
      { to: '/admin/orders', label: '订单', icon: ScrollText, end: true },
    ],
  },
] as const

/**
 * 左侧可折叠导航（handoff 第 3 屏）：展开 232px / 收起 66px，粘顶全高，
 * 右侧 1px 细线。当前项 = accent-wash 底 + 赤陶字；收起时组标签变细线。
 * 管理员登录时主导航替换为管理后台菜单（不显示普通功能）。
 */
export function Sidebar() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('sidebarCollapsed') === '1',
  )
  const { data: user } = useAuth()
  const { isMember, expiresAt } = useMembership()
  const navigate = useNavigate()

  const groups = user?.role === 'admin' ? ADMIN_GROUPS : GROUPS

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      navigate('/login')
    },
  })

  const toggle = () => {
    setCollapsed((v) => {
      localStorage.setItem('sidebarCollapsed', v ? '0' : '1')
      return !v
    })
  }

  return (
    <aside
      className="sticky top-0 flex h-svh shrink-0 flex-col border-r border-hairline transition-[width] duration-250 ease-out"
      style={{ width: collapsed ? 66 : 232 }}
    >
      {/* 顶部 64px：品牌 + 折叠按钮 */}
      <div
        className={cn(
          'flex h-16 shrink-0 items-center px-3.5',
          collapsed ? 'justify-center' : 'justify-between',
        )}
      >
        {!collapsed && (
          <NavLink
            to="/"
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
              <div className="px-3 pb-1 pt-4 text-[10.5px] font-bold tracking-[0.14em] text-quiet">
                {group.label}
              </div>
            )}
            {group.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-sm px-3 py-[9px] text-[14.5px] transition-colors',
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
            ))}
          </div>
        ))}
      </nav>

      {/* 底部：头像方块 + 用户名 + 登出 */}
      <div
        className={cn(
          'flex shrink-0 items-center gap-2.5 border-t border-hairline px-3.5 py-3.5',
          collapsed && 'justify-center px-0',
        )}
      >
        <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-tint text-[13px] text-muted-ink">
          {(user?.username ?? '?').slice(0, 1).toUpperCase()}
        </span>
        {!collapsed && (
          <div className="flex min-w-0 flex-col">
            <span className="flex items-center gap-1.5 truncate text-[14px] text-ink">
              {user?.username}
              {isMember && (
                <span
                  className="rounded-sm border border-accent/40 px-1 py-px text-[10px] leading-none text-accent"
                  title={expiresAt ? `会员有效期至 ${expiresAt.slice(0, 10)}` : undefined}
                >
                  会员
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
              className="self-start text-[12px] text-quiet transition-colors hover:text-accent"
            >
              登出
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}

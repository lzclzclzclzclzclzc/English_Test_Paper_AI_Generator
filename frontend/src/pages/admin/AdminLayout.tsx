import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/admin', label: '概览', end: true },
  { to: '/admin/users', label: '用户', end: false },
  { to: '/admin/memberships', label: '会员', end: true },
  { to: '/admin/orders', label: '订单', end: true },
]

export function AdminLayout() {
  return (
    <div className="mx-auto flex w-full max-w-[1040px] gap-8 p-8">
      <nav className="flex w-[140px] shrink-0 flex-col gap-0.5">
        <div className="px-3 pb-2 text-[10.5px] font-bold tracking-[0.14em] text-quiet">管理后台</div>
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              cn(
                'rounded-sm px-3 py-2 text-[14px] transition-colors',
                isActive ? 'bg-wash text-accent' : 'text-muted-ink hover:bg-tint hover:text-ink',
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  )
}

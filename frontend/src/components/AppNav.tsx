import { NavLink, useNavigate } from 'react-router-dom'
import { ScrollText } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { logout } from '@/api/auth'
import { useAuth } from '@/hooks/useAuth'
import { useMembership } from '@/hooks/useMembership'
import { queryClient } from '@/lib/queryClient'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const links = [
  { to: '/', label: '生成试卷' },
  { to: '/review', label: '错题复习' },
  { to: '/papers', label: '我的试卷' },
  { to: '/mastery', label: '掌握度' },
  { to: '/membership', label: '会员' },
] as const

/** 导航栏（Spec F § 5）：白底下边线、方形卷轴图标 logo、当前页 2px 下划线、头像圈。 */
export function AppNav() {
  const { data: user } = useAuth()
  const { isMember, expiresAt } = useMembership()
  const navigate = useNavigate()

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      navigate('/login')
    },
  })

  return (
    <header className="border-b border-line bg-sheet">
      <div className="mx-auto flex h-14 max-w-[880px] items-center justify-between px-6">
        <div className="flex items-center gap-6">
          <NavLink to="/" className="flex items-center gap-2.5">
            <span className="flex size-7 items-center justify-center rounded-[4px] bg-ink text-paper">
              <ScrollText className="size-4" strokeWidth={2} />
            </span>
            <span className="font-serif text-[15px] font-bold text-foreground">墨卷</span>
          </NavLink>
          <nav className="flex items-center gap-5">
            {links.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    'border-b-2 pb-0.5 text-[13.5px] transition-colors',
                    isActive
                      ? 'border-ink font-bold text-ink'
                      : 'border-transparent text-text-mid hover:text-foreground',
                  )
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {isMember && (
            <span
              className="rounded-full border border-[#b08d3e]/45 bg-[#faf6ec] px-2 py-0.5 text-[11px] font-medium text-[#8a6d2f]"
              title={expiresAt ? `会员有效期至 ${expiresAt.slice(0, 10)}` : undefined}
            >
              会员
            </span>
          )}
          {user && (
            <span
              className="flex size-8 items-center justify-center rounded-full bg-[#dfe6ee] text-[13px] font-medium text-ink"
              title={user.username}
            >
              {user.username.slice(0, 1).toUpperCase()}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
          >
            退出登录
          </Button>
        </div>
      </div>
    </header>
  )
}

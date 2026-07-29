import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useMembership } from '@/hooks/useMembership'
import { cn } from '@/lib/utils'

type Theme = 'light' | 'dark'

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  localStorage.setItem('theme', theme)
}

/** 设置（handoff 第 12 屏）：细线分隔的行式列表——账号 / 阅读外观 / 速率限制。 */
export function SettingsPage() {
  const { data: user } = useAuth()
  const { isMember, expiresAt } = useMembership()
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  )

  const registeredAt = user
    ? new Date(user.created_at).toLocaleDateString('zh-CN', { dateStyle: 'medium' })
    : ''

  return (
    <div className="max-w-[44rem]">
      <p className="text-[11px] tracking-[0.1em] text-quiet">SETTINGS</p>
      <div className="mb-10 mt-3 flex flex-col gap-3">
        <h1 className="text-[30px] font-normal leading-snug text-ink">设置</h1>
      </div>

      <div className="flex flex-col">
        {/* 账号 */}
        <section className="flex flex-col gap-2 border-t border-hairline py-7">
          <h2 className="text-[17px] text-ink">账号</h2>
          <p className="text-[14px] leading-[1.9] text-muted-ink">
            {user?.username} · {registeredAt} 注册 · 会话 30 天滑动过期
          </p>
          <p className="text-[13px] text-quiet">
            {isMember
              ? `会员有效期至 ${expiresAt ? expiresAt.slice(0, 10) : '—'}`
              : '未开通会员，出卷与解析按每日免费额度计'}
          </p>
        </section>

        {/* 阅读外观 */}
        <section className="flex flex-col gap-3 border-t border-hairline py-7">
          <h2 className="text-[17px] text-ink">阅读外观</h2>
          <div className="flex gap-2">
            {(
              [
                ['light', '纸色 Ink'],
                ['dark', '深墨地 Deep Ink'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={theme === value}
                onClick={() => {
                  setTheme(value)
                  applyTheme(value)
                }}
                className={cn(
                  'rounded-sm border px-4 py-2 text-[13.5px] transition-colors',
                  theme === value
                    ? 'border-accent bg-wash text-ink'
                    : 'border-hairline text-muted-ink hover:bg-tint hover:text-ink',
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="text-[13px] text-quiet">深色为暖炭墨地、亮赤陶强调，token 已内建，两套外观同一套组件。</p>
        </section>

        {/* 速率限制（只读） */}
        <section className="flex flex-col gap-2 border-y border-hairline py-7">
          <h2 className="text-[17px] text-ink">速率限制</h2>
          <p className="text-[14px] leading-[1.9] text-muted-ink">
            出卷 30 次 / 分钟 · 解析 60 次 / 分钟（服务端限流，对所有用户一致）
          </p>
        </section>
      </div>
    </div>
  )
}

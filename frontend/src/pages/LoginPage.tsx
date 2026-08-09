import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { login, register } from '@/api/auth'
import { ApiError } from '@/api/client'
import { PATHS } from '@/lib/paths'
import { queryClient } from '@/lib/queryClient'
import { cn } from '@/lib/utils'

/** 与后端 UserCredentials 严格对齐（backend-api.md）：边界改动必须两处同步。 */
const credentialsSchema = z.object({
  username: z
    .string()
    .min(3, '用户名至少 3 个字符')
    .max(32, '用户名最多 32 个字符')
    .regex(/^[a-zA-Z0-9_]+$/, '只允许英文字母、数字和下划线'),
  password: z.string().min(6, '密码至少 6 位').max(128, '密码最多 128 位'),
})

type Credentials = z.infer<typeof credentialsSchema>
type Mode = 'login' | 'register'

const inputClass =
  'w-full rounded-[3px] border border-ink-20 bg-transparent px-3 py-2.5 text-[15px] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent'

/** 登录 / 注册（handoff 第 2 屏）：左右两栏，中间竖细线，右栏 24rem 表单。 */
export function LoginPage() {
  const [mode, setMode] = useState<Mode>('login')
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? PATHS.dashboard

  const form = useForm<Credentials>({
    resolver: zodResolver(credentialsSchema),
    defaultValues: { username: '', password: '' },
  })

  const onSubmit = async (values: Credentials) => {
    try {
      // register 与 login 的响应都是 User 且都会 Set-Cookie（注册自动登录）
      const user = mode === 'login' ? await login(values) : await register(values)
      queryClient.setQueryData(['auth', 'me'], user)
      // 管理员未指定返回路径时直达管理后台；否则沿用 from（普通页会被 RedirectIfAdmin 兜回）
      const dest = from === PATHS.dashboard && user.role === 'admin' ? PATHS.admin : from
      navigate(dest, { replace: true })
    } catch (err) {
      if (
        err instanceof ApiError &&
        (err.payload.error_code === 'auth.invalid_credentials' ||
          err.payload.error_code === 'auth.username_conflict')
      ) {
        form.setError('root', { message: err.payload.message })
      } else {
        form.setError('root', { message: '登录服务暂时不可用，请稍后重试' })
      }
    }
  }

  return (
    <div className="grid min-h-svh grid-cols-[1.15fr_1fr] bg-background max-md:grid-cols-1">
      {/* 左栏：品牌 / 说明 / 底部小字 */}
      <div className="flex flex-col justify-between border-r border-hairline px-14 py-12 max-md:hidden">
        <Link
          to="/welcome"
          className="self-start text-[21px] tracking-[0.06em] text-ink [font-family:var(--font-display)]"
        >
          中考英语 AI 试卷生成器
        </Link>
        <p className="max-w-[24em] text-[26px] leading-[1.6] text-ink">
          说一句你想练什么，<mark>从真题库里出一份能直接做的卷子</mark>。
        </p>
        <p className="text-[12px] text-quiet">用户名 + 密码本地登录 · 会话 30 天滑动过期</p>
      </div>

      {/* 右栏：表单 */}
      <div className="flex items-center justify-center px-8 py-12">
        <div className="w-full max-w-[24rem]">
          {/* 登录 / 注册 tabs：选中项 2px 赤陶下边框 */}
          <div className="mb-8 flex gap-6 border-b border-hairline">
            {(
              [
                ['login', '登录'],
                ['register', '注册'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setMode(value)}
                className={cn(
                  '-mb-px border-b-2 pb-2.5 font-ui text-[15px] transition-colors',
                  mode === value
                    ? 'border-accent text-ink'
                    : 'border-transparent text-quiet hover:text-ink',
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <form className="flex flex-col gap-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="username" className="font-ui text-[13px] text-muted-ink">
                用户名
              </label>
              <input
                id="username"
                autoComplete="username"
                className={inputClass}
                {...form.register('username')}
              />
              {form.formState.errors.username && (
                <p className="text-[12px] text-accent">
                  {form.formState.errors.username.message}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="password" className="font-ui text-[13px] text-muted-ink">
                密码
              </label>
              <input
                id="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                className={inputClass}
                {...form.register('password')}
              />
              {form.formState.errors.password && (
                <p className="text-[12px] text-accent">
                  {form.formState.errors.password.message}
                </p>
              )}
            </div>

            <p className="font-ui text-[12px] tabular-nums text-quiet">3–32 位字母数字下划线 · 密码 6–128 位</p>

            {form.formState.errors.root && (
              <p className="text-[12px] text-accent">{form.formState.errors.root.message}</p>
            )}

            <button
              type="submit"
              disabled={form.formState.isSubmitting}
              className="rounded-sm border border-accent bg-wash py-2.5 font-ui text-[15px] tracking-[0.06em] text-ink transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-50"
            >
              {form.formState.isSubmitting
                ? mode === 'login'
                  ? '登录中…'
                  : '注册中…'
                : mode === 'login'
                  ? '登录'
                  : '注册'}
            </button>

            <Link
              to={PATHS.home}
              className="self-start font-ui text-[13px] text-quiet transition-colors hover:text-accent"
            >
              返回首页
            </Link>
          </form>
        </div>
      </div>
    </div>
  )
}

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

/** 登录 / 注册：variant-5 两栏——左深色品牌区，右方正表单。 */
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
          err.payload.error_code === 'auth.username_conflict' ||
          err.payload.error_code === 'auth.forbidden')
      ) {
        // 封禁账号（auth.forbidden）的具体原因在 detail 字段
        const hint =
          err.payload.error_code === 'auth.forbidden'
            ? String(err.payload.detail ?? '账号已被封禁')
            : err.payload.message
        form.setError('root', { message: hint })
      } else {
        form.setError('root', { message: '登录服务暂时不可用，请稍后重试' })
      }
    }
  }

  return (
    <div className="landing-swiss login-shell">
      {/* 左栏：深色品牌区 */}
      <div className="login-brand">
        <Link to={PATHS.home} className="brand">
          <span className="mark">卷</span>
          <span>卷王</span>
        </Link>
        <p className="login-pitch">
          说一句你想练什么，<span className="hl">从真题库里出一份能直接做的卷子</span>。
        </p>
        <p className="login-foot">用户名 + 密码本地登录 · 会话 30 天滑动过期</p>
      </div>

      {/* 右栏：表单 */}
      <div className="login-form-col">
        <div className="login-form">
          {/* 登录 / 注册 tabs：选中项 2px 橙红下边框 */}
          <div className="login-tabs">
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
                className={cn('login-tab', mode === value && 'is-active')}
              >
                {label}
              </button>
            ))}
          </div>

          <form className="flex flex-col gap-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="username" className="login-label">
                用户名
              </label>
              <input
                id="username"
                autoComplete="username"
                className="login-input"
                {...form.register('username')}
              />
              {form.formState.errors.username && (
                <p className="login-err">
                  {form.formState.errors.username.message}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="password" className="login-label">
                密码
              </label>
              <input
                id="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                className="login-input"
                {...form.register('password')}
              />
              {form.formState.errors.password && (
                <p className="login-err">
                  {form.formState.errors.password.message}
                </p>
              )}
            </div>

            <p className="login-hint num">3–32 位字母数字下划线 · 密码 6–128 位</p>

            {form.formState.errors.root && (
              <p className="login-err">{form.formState.errors.root.message}</p>
            )}

            <button
              type="submit"
              disabled={form.formState.isSubmitting}
              className="btn btn--primary btn--lg login-submit"
            >
              {form.formState.isSubmitting
                ? mode === 'login'
                  ? '登录中…'
                  : '注册中…'
                : mode === 'login'
                  ? '登录'
                  : '注册'}
            </button>

            <Link to={PATHS.home} className="login-back">
              返回首页
            </Link>
          </form>
        </div>
      </div>
    </div>
  )
}

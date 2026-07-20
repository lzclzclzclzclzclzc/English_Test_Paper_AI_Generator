import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ScrollText } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { login, register } from '@/api/auth'
import { ApiError } from '@/api/client'
import { queryClient } from '@/lib/queryClient'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

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

export function LoginPage() {
  const [mode, setMode] = useState<Mode>('login')
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const form = useForm<Credentials>({
    resolver: zodResolver(credentialsSchema),
    defaultValues: { username: '', password: '' },
  })

  const onSubmit = async (values: Credentials) => {
    try {
      // register 与 login 的响应都是 User 且都会 Set-Cookie（注册自动登录）
      const user = mode === 'login' ? await login(values) : await register(values)
      queryClient.setQueryData(['auth', 'me'], user)
      navigate(from, { replace: true })
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
    <div className="flex min-h-svh flex-col items-center justify-center gap-8 bg-background px-4">
      {/* 品牌 + slogan 在卡片外（Spec F § 5 登录页） */}
      <div className="flex flex-col items-center gap-2">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-[4px] bg-ink text-paper">
            <ScrollText className="size-6" strokeWidth={2} />
          </span>
          <span className="font-serif text-2xl font-bold text-foreground">墨卷</span>
        </div>
        <p className="text-[13px] text-muted-foreground">用你的话，出你的卷</p>
      </div>

      <Card className="w-full max-w-[400px]">
        <CardContent className="pt-6">
          <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
            <TabsList className="mb-5 grid w-full grid-cols-2">
              <TabsTrigger value="login">登录</TabsTrigger>
              <TabsTrigger value="register">注册</TabsTrigger>
            </TabsList>
          </Tabs>

          <form
            className="flex flex-col gap-4"
            onSubmit={form.handleSubmit(onSubmit)}
            noValidate
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                autoComplete="username"
                placeholder="3-32 位字母、数字或下划线"
                {...form.register('username')}
              />
              {form.formState.errors.username && (
                <p className="text-xs text-wrong">
                  {form.formState.errors.username.message}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                placeholder="至少 6 位"
                {...form.register('password')}
              />
              {form.formState.errors.password && (
                <p className="text-xs text-wrong">
                  {form.formState.errors.password.message}
                </p>
              )}
            </div>

            {form.formState.errors.root && (
              <p className="text-xs text-wrong">{form.formState.errors.root.message}</p>
            )}

            <Button type="submit" className="mt-1" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting
                ? mode === 'login'
                  ? '登录中…'
                  : '注册中…'
                : mode === 'login'
                  ? '登 录'
                  : '注 册'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

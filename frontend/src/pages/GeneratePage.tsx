import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getReadiness } from '@/api/health'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { GenerateForm, type GenerateFormValues } from '@/components/GenerateForm'
import { UpgradeDialog } from '@/components/UpgradeDialog'

/** 首页：只做新生成（fresh）。错题巩固 / 综合复习在「错题复习」页。 */
export function GeneratePage() {
  const [serverError, setServerError] = useState<string | null>(null)
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)

  const { generate, guard, isPending, locked, freeRemaining } = useGeneratePaper(setServerError)

  // 联调期后端题库/向量库可能未就绪；就绪时不渲染任何东西
  const readiness = useQuery({
    queryKey: ['health', 'ready'],
    queryFn: getReadiness,
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  })

  const handleSubmit = (values: GenerateFormValues) => {
    setServerError(null)
    const reason = guard('fresh')
    if (reason) {
      setUpgradeReason(reason)
      return
    }
    generate({ user_query: values.user_query, mode: 'fresh' })
  }

  return (
    <div className="mx-auto max-w-[880px] px-6 pt-12">
      <div className="mb-8 flex flex-col gap-1">
        <h1 className="font-serif text-2xl font-bold text-foreground">生成试卷</h1>
        <p className="text-[13.5px] text-text-mid">
          用一句话说出你想练的题型或考点，AI 会从真题库为你组一份卷
        </p>
      </div>
      {readiness.data?.status === 'not_ready' && (
        <div className="mb-4 rounded-md border border-line bg-[#faf8f3] px-4 py-2.5 text-[13px] text-text-mid">
          题库正在准备中，出卷可能暂时失败，可以稍后再试
        </div>
      )}
      <GenerateForm
        onSubmit={handleSubmit}
        isPending={isPending}
        serverError={serverError}
        quotaNotice={locked ? `今日免费出卷剩 ${freeRemaining} 次，开通会员不限次数` : null}
      />
      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}

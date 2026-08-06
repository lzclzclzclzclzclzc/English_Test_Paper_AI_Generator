import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getReadiness } from '@/api/health'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { GenerateForm, type GenerateFormValues } from '@/components/GenerateForm'
import { PageHeader } from '@/components/PageHeader'
import { generateQuotaNotice } from '@/lib/quota'
import { PipelineProgress } from '@/components/PipelineProgress'
import { UpgradeDialog } from '@/components/UpgradeDialog'

/** 生成试卷（handoff 第 4 屏）：只做新生成（fresh）。错题巩固 / 综合复习在「错题本」页。 */
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
    <div className="max-w-[52rem]">
      <PageHeader
        title="一句话出卷"
        intro={
          <>
            练习中心各面板能配出来的，这里一句话都能说到——还能说得更细。用一句话说出题型、
            考点、题量和改题力度，AI 会解析要求，从真题库检索、按力度改题，
            <mark>组一份能直接做的卷</mark>。
          </>
        }
      />
      {readiness.data?.status === 'not_ready' && (
        <div className="mb-6 max-w-[44rem] border-t border-accent pt-2.5 text-[13px] text-muted-ink">
          题库正在准备中，出卷可能暂时失败，可以稍后再试
        </div>
      )}
      <GenerateForm
        onSubmit={handleSubmit}
        isPending={isPending}
        serverError={serverError}
        quotaNotice={generateQuotaNotice(locked, freeRemaining)}
      />
      {isPending && <PipelineProgress />}
      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}

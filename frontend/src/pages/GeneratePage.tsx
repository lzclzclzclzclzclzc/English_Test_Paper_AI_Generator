import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getReadiness } from '@/api/health'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { GenerateForm, type GenerateFormValues } from '@/components/GenerateForm'
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
      {/* 端点小标签（handoff：每屏标注对应接口，上线可去掉） */}
      <p className="text-[11px] tracking-[0.1em] text-quiet">POST /API/PAPERS/GENERATE</p>
      <div className="mb-10 mt-3 flex flex-col gap-3">
        <h1 className="text-[30px] font-normal leading-snug text-ink">生成试卷</h1>
        <p className="max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
          用一句话说出你想练的题型或考点，AI 会解析你的要求，从真题库检索、按力度改题，组一份能直接做的卷。
        </p>
      </div>
      {readiness.data?.status === 'not_ready' && (
        <div className="mb-6 max-w-[44rem] border-t border-accent pt-2.5 text-[13px] text-muted-ink">
          题库正在准备中，出卷可能暂时失败，可以稍后再试
        </div>
      )}
      <GenerateForm
        onSubmit={handleSubmit}
        isPending={isPending}
        serverError={serverError}
        quotaNotice={locked ? `今日免费出卷剩 ${freeRemaining} 次，开通会员不限次数` : null}
      />
      {isPending && <PipelineProgress />}
      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}

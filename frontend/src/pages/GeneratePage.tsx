import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { generatePaper } from '@/api/papers'
import { getReadiness } from '@/api/health'
import { ApiError } from '@/api/client'
import { toastApiError } from '@/lib/errors'
import { queryClient } from '@/lib/queryClient'
import type { GeneratePaperRequest } from '@/types/api'
import type { RemediationHandoff } from '@/types/app'
import { GenerateForm, type GenerateFormValues } from '@/components/GenerateForm'

export function GeneratePage() {
  const navigate = useNavigate()
  const location = useLocation()

  // D2：navigate state 只读一次存本地，挂载后立即清除 history state——
  // 防止刷新/后退复活过期错题（navigate 只能在 effect 里调用）。
  const [remediation, setRemediation] = useState<RemediationHandoff | null>(() => {
    const state = location.state as { remediation?: RemediationHandoff } | null
    return state?.remediation ?? null
  })
  useEffect(() => {
    if ((location.state as { remediation?: unknown } | null)?.remediation) {
      navigate('.', { replace: true, state: null })
    }
  }, [location.state, navigate])

  const [serverError, setServerError] = useState<string | null>(null)

  // 联调期后端题库/向量库可能未就绪；就绪时不渲染任何东西
  const readiness = useQuery({
    queryKey: ['health', 'ready'],
    queryFn: getReadiness,
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  })

  const generate = useMutation({
    mutationFn: generatePaper,
    onSuccess: (paper) => {
      // D1：塞缓存再导航，PaperPage 零请求命中
      queryClient.setQueryData(['paper', paper.paper_id], paper)
      queryClient.invalidateQueries({ queryKey: ['papers', 'list'] })
      navigate(`/papers/${paper.paper_id}`)
    },
    onError: (err) => {
      if (
        err instanceof ApiError &&
        (err.payload.error_code === 'ai.parser_failed' ||
          err.payload.error_code === 'ai.no_candidate')
      ) {
        setServerError(
          err.payload.error_code === 'ai.parser_failed'
            ? 'AI 没能理解这个需求，换个说法试试（如"来 5 道现在完成时的选择题"）'
            : '题库里找不到匹配的题，试着放宽题型或考点条件',
        )
      } else {
        toastApiError(err)
      }
    },
  })

  const handleSubmit = (values: GenerateFormValues) => {
    setServerError(null)
    const req: GeneratePaperRequest = {
      user_query: values.user_query,
      mode: values.mode,
    }
    if (values.mode === 'remediation' && remediation) {
      req.wrong_items = remediation.wrongItems
    }
    if (values.mode === 'review') {
      req.review_window_days = 30
    }
    generate.mutate(req)
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
        remediation={remediation}
        onDismissRemediation={() => setRemediation(null)}
        onSubmit={handleSubmit}
        isPending={generate.isPending}
        serverError={serverError}
      />
    </div>
  )
}

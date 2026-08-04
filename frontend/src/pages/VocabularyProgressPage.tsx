import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { getVocabularyProgress, updateVocabularySettings } from '@/api/vocabulary'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { queryClient } from '@/lib/queryClient'

export function VocabularyProgressPage() {
  const progress = useQuery({ queryKey: ['vocabulary', 'progress'], queryFn: getVocabularyProgress })
  const [limit, setLimit] = useState(20)
  useEffect(() => { if (progress.data) setLimit(progress.data.daily_new_limit) }, [progress.data])
  const update = useMutation({
    mutationFn: () => updateVocabularySettings(limit),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['vocabulary'] }),
  })

  if (progress.isLoading) return <Skeleton className="h-64 w-full" />
  if (progress.isError || !progress.data) return <div className="border-t border-hairline pt-8 text-sm text-muted-ink">进度加载失败，请稍后重试。</div>
  const data = progress.data
  const stats = [
    ['今日新词', `${data.new_completed}`],
    ['今日复习', `${data.review_completed}`],
    ['待复习', `${data.due_count}`],
    ['已掌握', `${data.mastered_count} / ${data.total_words}`],
    ['连续学习', `${data.streak_days} 天`],
  ]
  return (
    <div className="max-w-[56rem]">
      <PageHeader title="背词进度" intro="词汇学习与语法掌握度分开记录；按固定间隔安排下一次复习。" />
      <div className="grid gap-px overflow-hidden border border-hairline bg-hairline sm:grid-cols-2 lg:grid-cols-5">
        {stats.map(([label, value]) => <div key={label} className="bg-canvas px-4 py-5"><p className="text-xs text-quiet">{label}</p><p className="mt-2 text-xl text-ink">{value}</p></div>)}
      </div>
      <section className="mt-10 max-w-md border-t border-hairline pt-7">
        <h2 className="text-lg text-ink [font-family:var(--font-display)]">每日新词目标</h2>
        <div className="mt-4 flex items-center gap-3">
          <input className="h-9 w-24 rounded-sm border border-hairline bg-transparent px-2 text-ink" type="number" min="10" max="50" value={limit} onChange={(event) => setLimit(Number(event.target.value))} />
          <span className="text-sm text-muted-ink">词 / 天（10–50）</span>
          <Button size="sm" disabled={update.isPending || limit < 10 || limit > 50} onClick={() => update.mutate()}>保存</Button>
        </div>
      </section>
      <p className="mt-10 text-xs leading-6 text-quiet">
        {data.wordlist_label}{data.source_url && <> · <a className="underline" href={data.source_url} target="_blank" rel="noreferrer">查看来源</a></>}
      </p>
    </div>
  )
}

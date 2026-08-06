import { useQuery } from '@tanstack/react-query'
import { listPapers } from '@/api/papers'
import type { MasteryProfile } from '@/types/api'
import { TYPE_LABELS, prettifyKp } from '@/lib/kp'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** 与 MasteryReport 相同的三色 band(Spec F v2.2)。 */
const bandOf = (m: number) => (m < 0.4 ? 'weak' : m < 0.7 ? 'mid' : 'solid')
const BAND_TEXT: Record<string, string> = {
  weak: 'text-accent',
  mid: 'text-grammar',
  solid: 'text-success',
}
const BAND_LABEL: Record<string, string> = { weak: '薄弱', mid: '一般', solid: '扎实' }

/** 固定话术建议:纯前端模板,不耗 LLM。 */
function buildAdvice(profile: MasteryProfile): string[] {
  const advice: string[] = []
  const weakest = [...profile.weak_kps].sort((a, b) => a.mastery - b.mastery)[0]
  if (weakest && weakest.mastery < 0.4) {
    advice.push(
      `「${prettifyKp(weakest.knowledge_point_id)}」目前最薄弱，建议每天一组 8–10 题专项，连续三天后回来看变化。`,
    )
  } else if (weakest) {
    advice.push(
      `「${prettifyKp(weakest.knowledge_point_id)}」还有提升空间，可以隔天安排一组专项巩固。`,
    )
  }
  const domType = profile.dominant_types[0]
  if (domType) {
    advice.push(
      `错题最集中的题型是${TYPE_LABELS[domType] ?? domType}，做错后建议逐题看 AI 讲解，弄清为什么错。`,
    )
  }
  advice.push('保持每天一练的节奏；交卷后把错题收进错题本，周末用错题重练查漏补缺。')
  return advice
}

interface StudyReportProps {
  profile: MasteryProfile
  windowLabel: string
  onClose: () => void
}

/**
 * 学情报告(会员):一页纸给家长——练习量、薄弱考点、下一步建议。
 * 打印时页面其他部分由 MasteryPage 的 print:hidden 隐藏,只留本报告。
 */
export function StudyReport({ profile, windowLabel, onClose }: StudyReportProps) {
  // 报告打开时才拉试卷列表,只为统计练卷数(近 100 份)
  const papers = useQuery({
    queryKey: ['papers', 'report-count'],
    queryFn: () => listPapers(100, 0),
    staleTime: 60_000,
  })
  const paperCount = papers.data?.items.length ?? null
  const submittedCount = papers.data?.items.filter((p) => p.submitted).length ?? null

  const weakest = [...profile.weak_kps].sort((a, b) => a.mastery - b.mastery).slice(0, 5)
  const today = new Date().toLocaleDateString('zh-CN', { dateStyle: 'long' })

  return (
    <section className="kk-rise mt-10 border-t border-accent pt-6 print:mt-0 print:border-t-0 print:pt-0">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-[28px] leading-snug text-ink [font-family:var(--font-display)]">
            学情报告
          </h2>
          <p className="text-[12.5px] text-quiet">
            {today} 生成 · 统计窗口：{windowLabel}
          </p>
        </div>
        <div className="flex items-center gap-2.5 print:hidden">
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            打印这份报告
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose}>
            收起
          </Button>
        </div>
      </div>

      {/* 练习量 */}
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4 border-b border-hairline pb-6 font-ui">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] font-[550] tracking-[0.1em] text-quiet">纳入作答</span>
          <span className="text-[32px] font-[750] leading-none tabular-nums text-ink">
            {profile.total_attempts_considered}
            <span className="text-[13px] font-[450] text-quiet"> 题次</span>
          </span>
        </div>
        {paperCount !== null && (
          <div className="flex flex-col gap-1">
            <span className="text-[11px] font-[550] tracking-[0.1em] text-quiet">生成试卷</span>
            <span className="text-[32px] font-[750] leading-none tabular-nums text-ink">
              {paperCount}
              <span className="text-[13px] font-[450] text-quiet">
                {' '}
                份 · 已交 {submittedCount}
              </span>
            </span>
          </div>
        )}
        <div className="flex flex-col gap-1">
          <span className="text-[11px] font-[550] tracking-[0.1em] text-quiet">覆盖考点</span>
          <span className="text-[32px] font-[750] leading-none tabular-nums text-ink">
            {profile.weak_kps.length}
            <span className="text-[13px] font-[450] text-quiet"> 个</span>
          </span>
        </div>
      </div>

      {/* 薄弱考点 */}
      <div className="mt-6">
        <h3 className="text-[15px] text-ink">最需要关注的考点</h3>
        {weakest.length === 0 ? (
          <p className="mt-2 text-[13.5px] text-muted-ink">
            这个窗口内还没有足够的答题记录。
          </p>
        ) : (
          <div className="mt-2 flex flex-col divide-y divide-ink-10 border-y border-hairline">
            {weakest.map((kp) => {
              const band = bandOf(kp.mastery)
              return (
                <div
                  key={kp.knowledge_point_id}
                  className="flex items-baseline justify-between gap-4 py-2.5"
                >
                  <span className="text-[14px] text-ink">
                    {prettifyKp(kp.knowledge_point_id)}
                  </span>
                  <span className="flex items-baseline gap-3 font-ui">
                    <span className={cn('text-[12px]', BAND_TEXT[band])}>
                      {BAND_LABEL[band]}
                    </span>
                    <span
                      className={cn(
                        'text-[15px] font-[650] tabular-nums',
                        BAND_TEXT[band],
                      )}
                    >
                      {Math.round(kp.mastery * 100)}
                      <span className="text-[11px] font-[450]">%</span>
                    </span>
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* 建议 */}
      <div className="mt-6">
        <h3 className="text-[15px] text-ink">下一步建议</h3>
        <ul className="mt-2 flex flex-col gap-1.5 text-[14px] leading-[1.9] text-muted-ink">
          {buildAdvice(profile).map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </div>

      <p className="mt-8 border-t border-hairline pt-3 text-[11.5px] text-quiet">
        由中考英语 AI 试卷生成器生成 · 掌握度按 Wilson 下界计算，分数越低越值得优先练
      </p>
    </section>
  )
}

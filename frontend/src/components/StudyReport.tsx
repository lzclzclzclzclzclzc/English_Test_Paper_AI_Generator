import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { listPapers } from '@/api/papers'
import { getVocabularyDaily, getVocabularyProgress } from '@/api/vocabulary'
import type { MasteryProfile } from '@/types/api'
import { TYPE_LABELS, prettifyKp } from '@/lib/kp'
import { bandOf, BAND_LABEL, masteryToOutline } from '@/lib/masteryOutline'
import { Button } from '@/components/ui/button'
import { MindmapView } from '@/components/mindmap/MindmapView'
import { cn } from '@/lib/utils'

const ACCENT = '#ef4a2b'

/** band 文字色（配套 lib/masteryOutline 的三色分级，仅本报告表格用）。 */
const BAND_TEXT: Record<string, string> = {
  weak: 'text-accent',
  mid: 'text-grammar',
  solid: 'text-success',
}

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
  /** 内联嵌入时的「收起」;/report 独立页不传,不渲染收起按钮 */
  onClose?: () => void
  /** /report 页已有 PageHeader 作标题，报告自带的标题栏只在打印时出现 */
  titleOnlyInPrint?: boolean
}

/**
 * 学情报告:一页纸给家长——练习量、薄弱考点、下一步建议。
 * 打印时宿主页面(/report)其他部分用 print:hidden 隐藏,只留本报告。
 */
export function StudyReport({ profile, windowLabel, onClose, titleOnlyInPrint }: StudyReportProps) {
  // 报告打开时才拉试卷列表,只为统计练卷数(近 100 份)
  const papers = useQuery({
    queryKey: ['papers', 'report-count'],
    queryFn: () => listPapers(100, 0),
    staleTime: 60_000,
  })
  const paperCount = papers.data?.items.length ?? null
  const submittedCount = papers.data?.items.filter((p) => p.submitted).length ?? null

  // 背词每日词量（与管理端用户详情页同款可视化）；窗口随报告的掌握度窗口。
  const vocabDays = profile.window_days ?? 0
  const vocabQuery = useQuery({
    queryKey: ['vocabulary', 'daily', vocabDays],
    queryFn: () => getVocabularyDaily(vocabDays),
    staleTime: 60_000,
  })
  const vocab = (vocabQuery.data?.items ?? []).map((d) => ({
    day: d.day.slice(5), // MM-DD
    new_words: d.new_words,
    review_words: d.review_words,
    studied: d.studied,
  }))
  const vocabTotal = vocab.reduce((sum, d) => sum + d.studied, 0)

  // 背词累计画像：已学习 / 长期掌握 / 连续学习天数（与背词进度页同源缓存）。
  const vocabProgress = useQuery({
    queryKey: ['vocabulary', 'progress'],
    queryFn: getVocabularyProgress,
    staleTime: 60_000,
  }).data
  const hasVocab = (vocabProgress?.learned_count ?? 0) > 0 || vocab.length > 0

  const weakest = [...profile.weak_kps].sort((a, b) => a.mastery - b.mastery).slice(0, 5)
  const today = new Date().toLocaleDateString('zh-CN', { dateStyle: 'long' })

  return (
    <section
      className={cn(
        'kk-rise print:mt-0 print:border-t-0 print:pt-0',
        titleOnlyInPrint ? 'mt-2' : 'mt-10 border-t border-accent pt-6',
      )}
    >
      <div
        className={cn(
          'mb-6 flex-wrap items-end justify-between gap-3',
          titleOnlyInPrint ? 'hidden print:flex' : 'flex',
        )}
      >
        <div className="flex flex-col gap-1">
          <h2 className="font-heading text-[28px] font-bold leading-snug text-ink">
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
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>
              收起
            </Button>
          )}
        </div>
      </div>

      {/* 练习量 */}
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4 border-b border-hairline pb-6 font-ui">
        <div className="flex flex-col gap-1">
          <span className="kicker">纳入作答</span>
          <span className="text-[32px] font-bold leading-none tabular-nums text-ink">
            {profile.total_attempts_considered}
            <span className="text-[13px] font-[450] text-quiet"> 题次</span>
          </span>
        </div>
        {paperCount !== null && (
          <div className="flex flex-col gap-1">
            <span className="kicker">生成试卷</span>
            <span className="text-[32px] font-bold leading-none tabular-nums text-ink">
              {paperCount}
              <span className="text-[13px] font-[450] text-quiet">
                {' '}
                份 · 已交 {submittedCount}
              </span>
            </span>
          </div>
        )}
        <div className="flex flex-col gap-1">
          <span className="kicker">覆盖考点</span>
          <span className="text-[32px] font-bold leading-none tabular-nums text-ink">
            {profile.weak_kps.length}
            <span className="text-[13px] font-[450] text-quiet"> 个</span>
          </span>
        </div>
        {profile.writing_graded_count > 0 && profile.writing_avg_score != null && (
          <div className="flex flex-col gap-1">
            <span className="kicker">写作平均分</span>
            <span className="text-[32px] font-bold leading-none tabular-nums text-ink">
              {profile.writing_avg_score}
              <span className="text-[13px] font-[450] text-quiet">
                {' '}
                / {profile.writing_full_score} 分 · {profile.writing_graded_count} 篇
              </span>
            </span>
          </div>
        )}
      </div>

      {/* 薄弱考点 */}
      <div className="mt-6">
        <h3 className="font-heading text-[15px] font-bold text-ink">最需要关注的考点</h3>
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
                        'text-[15px] font-bold tabular-nums',
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

      {/* 知识点掌握情况思维导图(hard code,只读)。交互式 SVG 打印易失真，
          打印时隐藏——薄弱考点表已用打印友好的形式覆盖同样的数据。 */}
      {profile.weak_kps.length > 0 && (
        <div className="mt-6 print:hidden">
          <h3 className="font-heading text-[15px] font-bold text-ink">掌握情况脑图</h3>
          <p className="mt-1 text-[12.5px] text-quiet">
            按掌握程度分为薄弱 / 一般 / 扎实三支，括号内为正确率。
          </p>
          <div className="mt-2 h-[300px] w-full overflow-hidden rounded-sm border border-hairline bg-card-surface">
            <MindmapView outline={masteryToOutline(profile)} />
          </div>
        </div>
      )}

      {/* 背单词情况（每日新学/复习词量，与管理端用户详情页同款）。交互式 SVG
          打印易失真，打印时隐藏。 */}
      {hasVocab && (
        <div className="mt-6 print:hidden">
          <h3 className="font-heading text-[15px] font-bold text-ink">背单词情况</h3>

          {vocabProgress && (
            <div className="mt-3 flex flex-wrap items-end gap-x-10 gap-y-4 font-ui">
              <div className="flex flex-col gap-1">
                <span className="kicker">已学习</span>
                <span className="text-[28px] font-bold leading-none tabular-nums text-ink">
                  {vocabProgress.learned_count}
                  <span className="text-[13px] font-[450] text-quiet"> / {vocabProgress.total_words} 词</span>
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="kicker">长期掌握</span>
                <span className="text-[28px] font-bold leading-none tabular-nums text-ink">
                  {vocabProgress.mastered_count}
                  <span className="text-[13px] font-[450] text-quiet"> 词</span>
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="kicker">连续学习</span>
                <span className="text-[28px] font-bold leading-none tabular-nums text-ink">
                  {vocabProgress.streak_days}
                  <span className="text-[13px] font-[450] text-quiet"> 天</span>
                </span>
              </div>
            </div>
          )}

          {vocab.length > 0 ? (
            <>
              <p className="mt-5 text-[12.5px] text-quiet">
                每日背词量（新学 / 复习），{windowLabel}内共 {vocabTotal} 词。
              </p>
              <div className="mt-2 h-[240px] w-full">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={vocab}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={32} />
                    <Tooltip />
                    <Bar dataKey="new_words" name="新学" stackId="v" fill={ACCENT} />
                    <Bar dataKey="review_words" name="复习" stackId="v" fill={ACCENT} fillOpacity={0.4} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          ) : (
            <p className="mt-4 text-[12.5px] text-quiet">{windowLabel}内暂无背词记录。</p>
          )}
        </div>
      )}

      {/* 建议 */}
      <div className="mt-6">
        <h3 className="font-heading text-[15px] font-bold text-ink">下一步建议</h3>
        <ul className="mt-2 flex flex-col gap-1.5 text-[14px] leading-[1.9] text-muted-ink">
          {buildAdvice(profile).map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </div>

      <p className="mt-8 border-t border-hairline pt-3 text-[11.5px] text-quiet">
        由卷王生成 · 掌握度按 Wilson 下界计算，分数越低越值得优先练
      </p>
    </section>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getQuestionBankStats } from '@/api/admin'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { prettifyKp, TYPE_LABELS } from '@/lib/kp'
import { Button } from '@/components/ui/button'
import { ChartCard, Metric } from '@/components/admin/ui'

const ACCENT = '#ef4a2b'
/** 图表最多展示的条目数（知识点/章节可能很多，取题量最少的 Top 更能暴露缺题）。 */
const TOP_N = 15

function EmptyChart() {
  return <p className="py-8 text-center text-[13px] text-quiet">暂无数据</p>
}

/** 题库统计（Spec H C1）：题目总数/题型数/覆盖知识点数 + 三组分布图（只读 questions.db）。 */
export function AdminQuestionBankPage() {
  useKnowledgePoints() // 确保考点中文名可用
  const stats = useQuery({
    queryKey: ['admin', 'questionbank', 'stats'],
    queryFn: () => getQuestionBankStats(),
  })

  const data = stats.data
  const byType = (data?.by_type ?? []).map((t) => ({
    name: TYPE_LABELS[t.question_type] ?? t.question_type,
    count: t.count,
  }))
  // 按题量升序：最缺题的知识点排最前，直接暴露"该补题了"
  const byKp = (data?.by_knowledge_point ?? [])
    .map((k) => ({ name: prettifyKp(k.knowledge_point_id), count: k.count }))
    .sort((a, b) => a.count - b.count)
    .slice(0, TOP_N)
  const byChapter = (data?.by_chapter ?? [])
    .map((c) => ({ name: `${c.chapter_l1}/${c.chapter_l2}`, count: c.count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, TOP_N)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">题库</h1>
        <Button variant="outline" size="sm" asChild>
          <Link to="/admin/questionbank/questions">浏览题目</Link>
        </Button>
      </div>

      {stats.isError && (
        <div className="flex items-center gap-3 rounded-md border border-hairline bg-wash/40 px-4 py-3">
          <p className="text-[13px] text-muted-ink">题库统计加载失败</p>
          <button className="text-[13px] text-accent hover:underline" onClick={() => stats.refetch()}>
            重试
          </button>
        </div>
      )}

      {stats.isLoading && <p className="text-[13px] text-quiet">加载中…</p>}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Metric label="题目总数" value={data.total} />
            <Metric label="题型数" value={data.by_type.length} />
            <Metric label="覆盖知识点" value={data.by_knowledge_point.length} />
          </div>

          <ChartCard title="分题型题量">
            {byType.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(160, byType.length * 44)}>
                <BarChart data={byType} margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--ink-10)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={36} />
                  <Tooltip />
                  <Bar dataKey="count" name="题量" fill={ACCENT} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ChartCard title={`题量最少的知识点（前 ${TOP_N}，指导补题）`}>
              {byKp.length === 0 ? (
                <EmptyChart />
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(160, byKp.length * 30)}>
                  <BarChart data={byKp} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} interval={0} />
                    <Tooltip />
                    <Bar dataKey="count" name="题量" fill={ACCENT} fillOpacity={0.75} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>

            <ChartCard title={`题量最多的章节（前 ${TOP_N}）`}>
              {byChapter.length === 0 ? (
                <EmptyChart />
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(160, byChapter.length * 30)}>
                  <BarChart data={byChapter} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" width={180} tick={{ fontSize: 11 }} interval={0} />
                    <Tooltip />
                    <Bar dataKey="count" name="题量" fill={ACCENT} fillOpacity={0.75} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>
        </>
      )}
    </div>
  )
}

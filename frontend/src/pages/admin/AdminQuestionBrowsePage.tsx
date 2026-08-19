import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { QuestionBankListItem } from '@/types/api'
import { searchQuestionBank } from '@/api/admin'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { prettifyKp, TYPE_LABELS } from '@/lib/kp'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/admin/Pagination'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const PAGE_SIZE = 20
const STEM_PREVIEW_LEN = 80

type Opt = { label?: unknown; text?: unknown }

/** 题干预览：截断前 80 字符（Spec H C2）。 */
function preview(stem: string): string {
  return stem.length > STEM_PREVIEW_LEN ? `${stem.slice(0, STEM_PREVIEW_LEN)}…` : stem
}

/** answer 字段按题型可能是字符串 / 列表 / 对象，统一渲染。 */
function AnswerView({ answer }: { answer: unknown }) {
  if (answer == null) return <span className="text-quiet">（无）</span>
  if (typeof answer === 'string') return <span className="font-ui text-ink">{answer}</span>
  return (
    <pre className="overflow-x-auto rounded-md bg-wash/60 p-2 font-ui text-[12.5px] text-ink">
      {JSON.stringify(answer, null, 2)}
    </pre>
  )
}

/** 单行题目：点击展开完整题干 + 选项 + 答案（答案默认折叠）。 */
function QuestionRow({ item }: { item: QuestionBankListItem }) {
  const [open, setOpen] = useState(false)
  const [showAnswer, setShowAnswer] = useState(false)
  const options = (item.options ?? []) as Opt[]

  return (
    <>
      <tr
        className="cursor-pointer border-b border-hairline hover:bg-tint/30"
        onClick={() => setOpen((v) => !v)}
      >
        <td className="px-3 py-2">
          {open ? (
            <ChevronDown className="size-4 text-quiet" />
          ) : (
            <ChevronRight className="size-4 text-quiet" />
          )}
        </td>
        <td className="px-3 py-2 font-ui text-[12px] text-muted-ink">{item.id}</td>
        <td className="px-3 py-2 text-muted-ink">{TYPE_LABELS[item.question_type] ?? item.question_type}</td>
        <td className="px-3 py-2 text-muted-ink">
          {item.book} · {item.chapter_l1}/{item.chapter_l2}
        </td>
        <td className="px-3 py-2 text-ink">{preview(item.stem)}</td>
      </tr>
      {open && (
        <tr className="border-b border-hairline bg-wash/30">
          <td />
          <td colSpan={4} className="px-3 py-3">
            <div className="flex flex-col gap-2">
              <p className="whitespace-pre-wrap text-[13px] text-ink">{item.stem}</p>
              {options.length > 0 && (
                <ul className="flex flex-col gap-1">
                  {options.map((o, i) => (
                    <li key={i} className="text-[13px] text-muted-ink">
                      <b className="font-ui text-ink">{String(o.label ?? '')}</b>{' '}
                      {String(o.text ?? '')}
                    </li>
                  ))}
                </ul>
              )}
              {item.knowledge_point_ids.length > 0 && (
                <p className="text-[12.5px] text-quiet">
                  知识点：{item.knowledge_point_ids.map(prettifyKp).join('、')}
                </p>
              )}
              <div className="flex items-start gap-3">
                {showAnswer ? (
                  <div className="min-w-0 flex-1">
                    <AnswerView answer={item.answer} />
                  </div>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowAnswer(true)
                    }}
                  >
                    显示答案
                  </Button>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

/** 题目浏览（Spec H C2）：筛选（题型/知识点/关键词）+ 分页表格 + 行展开详情。 */
export function AdminQuestionBrowsePage() {
  const kpCatalog = useKnowledgePoints() // 确保考点中文名可用（目录 + 注册映射）
  const [type, setType] = useState('')
  const [kp, setKp] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)

  const list = useQuery({
    queryKey: ['admin', 'questionbank', 'questions', type, kp, q, page],
    queryFn: () =>
      searchQuestionBank({
        type: type || undefined,
        kp: kp || undefined,
        q: q || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })

  /** 筛选变化联动重置分页（Spec H 7.3）。 */
  const onFilterChange = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v)
    setPage(1)
  }

  const items = list.data?.items ?? []
  const total = list.data?.total ?? 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] text-ink [font-family:var(--font-display)]">题目浏览</h1>
        <Button variant="outline" size="sm" asChild>
          <Link to="/admin/questionbank">题库统计</Link>
        </Button>
      </div>

      {/* 筛选栏 */}
      <div className="flex flex-wrap items-center gap-2">
        <Select value={type || 'all'} onValueChange={onFilterChange(setType)}>
          <SelectTrigger size="sm" aria-label="题型筛选" className="w-[130px] border-ink-20 font-ui text-[12.5px]">
            <SelectValue placeholder="全部题型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部题型</SelectItem>
            {Object.entries(TYPE_LABELS).map(([t, label]) => (
              <SelectItem key={t} value={t}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={kp || 'all'} onValueChange={onFilterChange(setKp)}>
          <SelectTrigger size="sm" aria-label="知识点筛选" className="w-[180px] border-ink-20 font-ui text-[12.5px]">
            <SelectValue placeholder="全部知识点" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部知识点</SelectItem>
            {(kpCatalog.data ?? []).map((k) => (
              <SelectItem key={k.id} value={k.id}>
                {k.level2}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          aria-label="题干关键词"
          className="h-8 w-56 font-ui text-[12.5px]"
          placeholder="题干关键词…"
          value={q}
          onChange={(e) => onFilterChange(setQ)(e.target.value)}
        />

        {(type || kp || q) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setType('')
              setKp('')
              setQ('')
              setPage(1)
            }}
          >
            清除筛选
          </Button>
        )}
      </div>

      {list.isError ? (
        <div className="flex items-center gap-3 rounded-md border border-hairline bg-wash/40 px-4 py-3">
          <p className="text-[13px] text-muted-ink">题目加载失败</p>
          <button className="text-[13px] text-accent hover:underline" onClick={() => list.refetch()}>
            重试
          </button>
        </div>
      ) : list.isLoading ? (
        <p className="text-[13px] text-quiet">加载中…</p>
      ) : items.length === 0 ? (
        <p className="py-8 text-center text-[13px] text-quiet">没有匹配的题目</p>
      ) : (
        <div className={cn('overflow-x-auto rounded-md border border-hairline', list.isFetching && 'opacity-60')}>
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-hairline text-quiet">
                <th className="w-8 px-3 py-2 font-normal" />
                <th className="px-3 py-2 font-normal">ID</th>
                <th className="px-3 py-2 font-normal">题型</th>
                <th className="px-3 py-2 font-normal">教材 / 章节</th>
                <th className="px-3 py-2 font-normal">题干</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <QuestionRow key={it.id} item={it} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />
    </div>
  )
}

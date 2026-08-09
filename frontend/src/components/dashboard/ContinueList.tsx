import { Link } from 'react-router-dom'
import { PATHS } from '@/lib/paths'
import type { PaperListItem } from '@/types/api'

const pad = (n: number) => String(n).padStart(2, '0')

/** 生成时间 → 「MM-DD HH:mm」 */
function fmtDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 继续作答：最近未交卷的前 2 份，整行可点进卷（无未交卷时由父级整块不渲染）。 */
export function ContinueList({ items }: { items: PaperListItem[] }) {
  return (
    <section className="flex flex-col gap-2">
      <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">继续作答</span>
      <div className="divide-y divide-ink-10">
        {items.map((p) => (
          <Link
            key={p.paper_id}
            to={PATHS.paper(p.paper_id)}
            className="group flex items-baseline gap-4 px-2 py-3.5 transition-colors hover:bg-tint"
          >
            <span className="min-w-0 flex-1 truncate text-[14.5px] text-ink">{p.title}</span>
            <span className="shrink-0 font-mono text-[12px] text-quiet">
              {fmtDate(p.generated_at)}
            </span>
            <span className="shrink-0 font-ui text-[13px] text-quiet transition-colors group-hover:text-accent">
              继续 →
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}

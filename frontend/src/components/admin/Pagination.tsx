import { Button } from '@/components/ui/button'

/** 总页数（至少 1 页）；0 条时为 1 但组件不渲染。导出供逻辑测试复用。 */
export function pageCountOf(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize))
}

/** 管理后台通用分页控件（Spec H A1）：上一页/下一页 + 页码指示。 */
export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number
  pageSize: number
  total: number
  onChange: (page: number) => void
}) {
  const pageCount = pageCountOf(total, pageSize)
  if (total === 0) return null
  return (
    <div className="flex items-center justify-center gap-3 pt-3 text-[13px] text-muted-ink">
      <Button
        variant="outline"
        size="sm"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        上一页
      </Button>
      <span className="tabular-nums">
        第 {page} / {pageCount} 页 · 共 {total} 条
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={page >= pageCount}
        onClick={() => onChange(page + 1)}
      >
        下一页
      </Button>
    </div>
  )
}

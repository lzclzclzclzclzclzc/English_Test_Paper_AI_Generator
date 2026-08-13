import { useEffect, useRef, useState } from 'react'
import { MindmapView } from './MindmapView'

interface Props {
  /** 当前大纲（父组件持有，对话改图后更新此值即同步预览+编辑框） */
  value: string
  /** debounce 后回调，父组件据此 PATCH 落库 */
  onSave: (outline: string) => void
  /** 保存中指示（可选） */
  saving?: boolean
}

const DEBOUNCE_MS = 600

/** 大纲编辑器：左编辑 markdown、右实时预览，停止输入 600ms 后自动保存。 */
export function MindmapEditor({ value, onSave, saving }: Props) {
  const [draft, setDraft] = useState(value)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSaved = useRef(value)

  // 外部 value 变化（如对话改图 / 首次加载）→ 同步进编辑框
  useEffect(() => {
    setDraft(value)
    lastSaved.current = value
  }, [value])

  const onChange = (next: string) => {
    setDraft(next)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      if (next !== lastSaved.current) {
        lastSaved.current = next
        onSave(next)
      }
    }, DEBOUNCE_MS)
  }

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 md:flex-row">
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="mb-1 flex items-center justify-between">
          <span className="font-ui text-[12.5px] text-quiet">大纲（Markdown）</span>
          <span className="font-ui text-[12px] text-quiet">
            {saving ? '保存中…' : '已自动保存'}
          </span>
        </div>
        <textarea
          value={draft}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
          className="min-h-[200px] flex-1 resize-none rounded-[10px] border border-ink-20 bg-transparent p-3 font-mono text-[13px] leading-[1.7] text-ink outline-none focus:border-accent"
        />
      </div>
      <div className="min-h-[240px] flex-1 rounded-[10px] border border-hairline bg-tint/40">
        <MindmapView outline={draft} />
      </div>
    </div>
  )
}

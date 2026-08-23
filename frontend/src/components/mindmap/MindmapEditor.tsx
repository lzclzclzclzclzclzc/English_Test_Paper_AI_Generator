import { useEffect, useRef, useState } from 'react'

const DEBOUNCE_MS = 600

/**
 * 大纲草稿 + 自动保存 hook：父组件持有 draft，编辑框与预览共用同一份实时草稿。
 * 停止输入 600ms 后回调 onSave 落库；外部 value 变化（对话改图 / 首次加载）同步进 draft。
 */
export function useOutlineDraft(value: string, onSave: (outline: string) => void) {
  const [draft, setDraft] = useState(value)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSaved = useRef(value)

  // 外部 value 变化（如对话改图 / 首次加载）→ 同步进编辑框。
  // 仅当内容确实不同才覆盖 draft，避免自动保存回环（父层 PATCH 后回传同值）
  // 重置光标或吞掉用户新输入。
  useEffect(() => {
    setDraft((cur) => (cur === value ? cur : value))
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

  return { draft, onChange }
}

interface OutlineEditorProps {
  /** 当前草稿（来自 useOutlineDraft） */
  draft: string
  /** 输入回调（来自 useOutlineDraft） */
  onChange: (outline: string) => void
  /** 保存中指示（可选） */
  saving?: boolean
}

/** 大纲编辑列：仅 markdown 文本框（预览由父层常驻居中渲染，不在此）。 */
export function OutlineEditor({ draft, onChange, saving }: OutlineEditorProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
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
        aria-label="大纲 Markdown 编辑器"
        className="min-h-[200px] flex-1 resize-none rounded-sm border border-ink-20 bg-transparent p-3 font-mono text-[13px] leading-[1.7] text-ink outline-none focus:border-accent"
      />
    </div>
  )
}

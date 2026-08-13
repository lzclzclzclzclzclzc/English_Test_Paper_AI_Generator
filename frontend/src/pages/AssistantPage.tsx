import { useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { AssistantChat } from '@/components/AssistantChat'

const SUGGESTIONS = [
  '来 5 道现在完成时的选择题',
  '来 4 道词形转换题',
  '帮我制定 7 天学习计划',
  '用思维导图讲讲现在完成时',
] as const

/** 学习助手页：全局会话，复用 AssistantChat。 */
export function AssistantPage() {
  const location = useLocation()
  // 其他页面（如学习计划空态）可通过 location.state.prefill 预填输入框；只填不发。
  // 只在首次挂载时读取，读后清掉 history state，刷新不重复预填。
  const initialInputRef = useRef<string | undefined>(undefined)
  if (initialInputRef.current === undefined) {
    const prefill = (location.state as { prefill?: unknown } | null)?.prefill
    if (typeof prefill === 'string' && prefill.trim() !== '') {
      initialInputRef.current = prefill
      window.history.replaceState({}, '')
    } else {
      initialInputRef.current = ''
    }
  }
  const initialInput = initialInputRef.current || undefined

  return (
    <div className="-mb-12 flex h-[calc(100svh-2.5rem)] w-full flex-col">
      <AssistantChat
        scope="global"
        storageKey="agent.chat"
        allowClear
        initialInput={initialInput}
        emptyHeader={
          <>
            <h1 className="text-[30px] font-bold leading-tight tracking-[-0.01em] text-ink [font-family:var(--font-display)]">
              学习助手
            </h1>
            <p className="max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
              用一句话告诉我你想做什么：出题、查例题、制定学习计划、画思维导图，做好的卷子和导图
              <mark>直接给你入口</mark>。
            </p>
          </>
        }
        suggestions={SUGGESTIONS}
      />
    </div>
  )
}

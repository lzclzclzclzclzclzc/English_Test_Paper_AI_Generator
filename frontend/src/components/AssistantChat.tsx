import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { agentChat, clearAgentSession } from '@/api/agent'
import { toastApiError } from '@/lib/errors'
import { Button } from '@/components/ui/button'
import type { AgentAction } from '@/types/api'

interface ChatMessage {
  role: 'user' | 'assistant' | 'error'
  content: string
  action?: AgentAction | null
}

export interface AssistantChatProps {
  scope: 'global' | 'mindmap'
  storageKey: string
  mindmapId?: string
  sessionToken?: string
  /** 外部预填输入框（如学习计划空态导航进入），只填不发 */
  initialInput?: string
  /** 收到 agent 动作时回调（如详情页据 mindmap_updated 刷新） */
  onAction?: (action: AgentAction) => void
  /** 是否允许「新对话」（global 场景显示；mindmap 面板通常隐藏） */
  allowClear?: boolean
  /** 空态提示语 */
  emptyHint?: string
  /** 建议 prompt 列表 */
  suggestions?: readonly string[]
}

const stripInternalTags = (text: string) =>
  text
    .replace(/<paper_ready[^>]*\/?>/g, '')
    .replace(/<mindmap_ready[^>]*\/?>/g, '')
    .replace(/<mindmap_updated\s*\/?>/g, '')
    .trim()

function loadMessages(key: string): ChatMessage[] {
  try {
    const raw = sessionStorage.getItem(key)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed?.messages)) return parsed.messages
    }
  } catch { /* ignore */ }
  return []
}

function saveMessages(key: string, messages: ChatMessage[]) {
  try {
    sessionStorage.setItem(key, JSON.stringify({ messages }))
  } catch { /* ignore */ }
}

/** 可复用学习助手聊天。global = 全局会话；mindmap = 编辑页独立会话（session_token 隔离）。 */
export function AssistantChat({
  scope, storageKey, mindmapId, sessionToken, initialInput, onAction,
  allowClear = false, emptyHint, suggestions,
}: AssistantChatProps) {
  const navigate = useNavigate()
  const [input, setInput] = useState(initialInput ?? '')
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadMessages(storageKey))
  const bottomRef = useRef<HTMLDivElement>(null)

  const chatMutation = useMutation({
    mutationFn: agentChat,
    onSuccess: (res) => {
      setMessages((prev) => {
        const updated = [...prev, { role: 'assistant' as const, content: res.reply, action: res.action }]
        saveMessages(storageKey, updated)
        return updated
      })
      if (res.action) onAction?.(res.action)
    },
    onError: (err) => {
      setMessages((prev) => {
        const updated = [...prev, { role: 'error' as const, content: '出错了，请稍后重试或换个说法' }]
        saveMessages(storageKey, updated)
        return updated
      })
      toastApiError(err)
    },
  })

  const clearMutation = useMutation({
    mutationFn: clearAgentSession,
    onSuccess: () => { setMessages([]); saveMessages(storageKey, []) },
    onError: toastApiError,
  })

  const isPending = chatMutation.isPending

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isPending])

  const send = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || chatMutation.isPending) return
    setInput('')
    setMessages((prev) => {
      const updated = [...prev, { role: 'user' as const, content: trimmed }]
      saveMessages(storageKey, updated)
      return updated
    })
    chatMutation.mutate(
      scope === 'mindmap'
        ? { message: trimmed, scope, mindmap_id: mindmapId, session_token: sessionToken }
        : { message: trimmed },
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      {allowClear && messages.length > 0 && (
        <div className="flex min-h-5 items-center justify-end">
          <button
            type="button"
            disabled={clearMutation.isPending || chatMutation.isPending}
            onClick={() => clearMutation.mutate()}
            className="font-ui text-[12.5px] text-quiet transition-colors hover:text-accent disabled:opacity-50"
          >
            {clearMutation.isPending ? '清空中…' : '＋ 新对话'}
          </button>
        </div>
      )}

      <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto py-4">
        {messages.length === 0 && (
          <div className="flex flex-col gap-3 pt-6">
            {emptyHint && <p className="text-[14px] leading-[1.9] text-muted-ink">{emptyHint}</p>}
            {suggestions && (
              <div className="mt-1 flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button key={s} type="button"
                    className="rounded-sm border border-hairline px-3 py-1 font-ui text-[12.5px] text-muted-ink transition-colors hover:border-accent hover:bg-tint hover:text-accent"
                    onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex flex-col gap-6">
          {messages.map((msg, i) => {
            if (msg.role === 'user') {
              return (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[85%] whitespace-pre-wrap bg-wash px-4 py-2.5 text-[14.5px] leading-[1.8] text-ink" style={{ borderRadius: '14px' }}>
                    {msg.content}
                  </p>
                </div>
              )
            }
            const action = msg.action ?? null
            return (
              <div key={i} className="border-b border-hairline pb-6 last:border-b-0">
                {msg.role === 'error' ? (
                  <p className="text-[13.5px] text-accent">{msg.content}</p>
                ) : (
                  <div className="chat-md text-[14.5px] leading-[1.9] text-ink">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {stripInternalTags(msg.content)}
                    </ReactMarkdown>
                  </div>
                )}
                {action?.type === 'open_paper' && (
                  <div className="mt-4">
                    <Button size="sm" onClick={() => navigate(`/papers/${action.paper_id}`)}>
                      开始做题 →
                    </Button>
                  </div>
                )}
                {action?.type === 'open_mindmap' && (
                  <div className="mt-4">
                    <Button size="sm" onClick={() => navigate(`/mindmaps/${action.mindmap_id}`)}>
                      打开并编辑思维导图 →
                    </Button>
                  </div>
                )}
              </div>
            )
          })}
          {isPending && (
            <div className="flex items-center gap-2 font-ui text-[13px] text-quiet">
              <span className="kk-pulse size-2 rounded-full bg-accent" />
              思考中…
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-hairline pb-4 pt-3">
        <div className="flex items-stretch gap-3">
          <textarea
            rows={1}
            placeholder="输入你的需求，Enter 发送，Shift+Enter 换行"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isPending}
            className="min-h-[48px] flex-1 resize-none border border-ink-20 bg-transparent px-3.5 py-2.5 text-[14.5px] leading-[1.6] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent disabled:opacity-60"
            style={{ borderRadius: '10px' }}
          />
          <button
            type="button"
            disabled={isPending || !input.trim()}
            onClick={() => send(input)}
            className="shrink-0 border border-accent bg-accent px-6 font-ui text-[14.5px] font-bold tracking-[0.05em] text-white transition-colors hover:bg-accent-ink hover:border-accent-ink disabled:pointer-events-none disabled:opacity-50"
            style={{ borderRadius: '10px' }}
          >
            {chatMutation.isPending ? '思考中…' : '发送'}
          </button>
        </div>
      </div>
    </div>
  )
}

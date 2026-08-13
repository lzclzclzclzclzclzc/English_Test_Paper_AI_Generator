import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
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

const SUGGESTIONS = [
  '来 5 道现在完成时的选择题',
  '来 4 道词形转换题',
  '帮我制定 7 天学习计划',
  '查一下介词的例题',
] as const

// 仅缓存展示用的消息列表；真正的对话上下文由后端 SQLiteSession 按用户维护。
const SESSION_KEY = 'agent.chat'

/** 后端 agent 偶尔把内部信令标记（<paper_ready …/>）留在回复文本里，展示前滤掉。 */
const stripInternalTags = (text: string) => text.replace(/<paper_ready[^>]*\/?>/g, '').trim()

function loadMessages(): ChatMessage[] {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed?.messages)) return parsed.messages
    }
  } catch { /* ignore */ }
  return []
}

function saveMessages(messages: ChatMessage[]) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ messages }))
  } catch { /* ignore */ }
}

/**
 * 学习助手（dev 的 agent 对话，喫茶去外观）：用户消息 = accent-wash 底右对齐，
 * 助手消息 = 无框正文 + 底部细线；工具可出卷（open_paper 动作）、查例题、制定学习计划。
 */
export function AssistantPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages)
  const bottomRef = useRef<HTMLDivElement>(null)

  // 其他页面(如学习计划空态)可通过 location.state.prefill 预填输入框;
  // 只填不发,发送权留给用户。读取后清掉 state,刷新不重复预填。
  useEffect(() => {
    const prefill = (location.state as { prefill?: unknown } | null)?.prefill
    if (typeof prefill === 'string' && prefill.trim() !== '') {
      setInput(prefill)
      window.history.replaceState({}, '')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const chatMutation = useMutation({
    mutationFn: agentChat,
    onSuccess: (res) => {
      setMessages((prev) => {
        const updated = [...prev, { role: 'assistant' as const, content: res.reply, action: res.action }]
        saveMessages(updated)
        return updated
      })
    },
    onError: (err) => {
      setMessages((prev) => {
        const updated = [...prev, { role: 'error' as const, content: '出错了，请稍后重试或换个说法' }]
        saveMessages(updated)
        return updated
      })
      toastApiError(err)
    },
  })

  const clearMutation = useMutation({
    mutationFn: clearAgentSession,
    onSuccess: () => {
      setMessages([])
      saveMessages([])
    },
    onError: toastApiError,
  })

  const isPending = chatMutation.isPending

  // 滚到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isPending])

  const send = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || chatMutation.isPending) return
    setInput('')
    setMessages((prev) => {
      const updated = [...prev, { role: 'user' as const, content: trimmed }]
      saveMessages(updated)
      return updated
    })
    chatMutation.mutate({ message: trimmed })
  }

  const startNewChat = () => {
    if (chatMutation.isPending || clearMutation.isPending) return
    clearMutation.mutate()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="-mb-12 flex h-[calc(100svh-2.5rem)] w-full flex-col">
      {/* 顶行：新对话（有消息时显示） */}
      <div className="flex min-h-5 items-center justify-end">
        {messages.length > 0 && (
          <button
            type="button"
            disabled={clearMutation.isPending || chatMutation.isPending}
            onClick={startNewChat}
            className="font-ui text-[12.5px] text-quiet transition-colors hover:text-accent disabled:opacity-50"
          >
            {clearMutation.isPending ? '清空中…' : '＋ 新对话'}
          </button>
        )}
      </div>

      {/* 消息列表 */}
      <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto py-6">
        {messages.length === 0 && (
          <div className="flex flex-col gap-3 pt-10">
            <h1 className="text-[30px] font-bold leading-tight tracking-[-0.01em] text-ink [font-family:var(--font-display)]">
              学习助手
            </h1>
            <p className="max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
              用一句话告诉我你想做什么：出题、查例题、制定学习计划，做好的卷子
              <mark>直接给你入口</mark>。
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="rounded-sm border border-hairline px-3 py-1 font-ui text-[12.5px] text-muted-ink transition-colors hover:border-accent hover:bg-tint hover:text-accent"
                  onClick={() => send(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-6">
          {messages.map((msg, i) =>
            msg.role === 'user' ? (
              <div key={i} className="flex justify-end">
                <p className="max-w-[85%] whitespace-pre-wrap bg-wash px-4 py-2.5 text-[14.5px] leading-[1.8] text-ink" style={{ borderRadius: '14px' }}>
                  {msg.content}
                </p>
              </div>
            ) : (
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
                {msg.action?.type === 'open_paper' && (
                  <div className="mt-4">
                    <Button size="sm" onClick={() => navigate(`/papers/${(msg.action as Extract<AgentAction, { type: 'open_paper' }>).paper_id}`)}>
                      开始做题 →
                    </Button>
                  </div>
                )}
              </div>
            ),
          )}

          {/* 思考中：赤陶脉冲点 */}
          {isPending && (
            <div className="flex items-center gap-2 font-ui text-[13px] text-quiet">
              <span className="kk-pulse size-2 rounded-full bg-accent" />
              思考中…
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="border-t border-hairline pb-5 pt-4">
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

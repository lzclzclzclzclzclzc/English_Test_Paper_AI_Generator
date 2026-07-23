import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { agentChat, clearAgentSession } from '@/api/agent'
import { toastApiError } from '@/lib/errors'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
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

// 仅缓存展示用的气泡列表；真正的对话上下文由后端 SQLiteSession 按用户维护。
const SESSION_KEY = 'agent.chat'

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

export function GeneratePage() {
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages)
  const bottomRef = useRef<HTMLDivElement>(null)

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
    <div className="mx-auto -mb-16 flex h-[calc(100svh-3.5rem)] max-w-[800px] flex-col px-4">
      {/* 顶栏：新对话（仅有消息时显示） */}
      {messages.length > 0 && (
        <div className="flex justify-end pt-3">
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-text-mid"
            disabled={clearMutation.isPending || chatMutation.isPending}
            onClick={startNewChat}
          >
            {clearMutation.isPending ? '清空中…' : '＋ 新对话'}
          </Button>
        </div>
      )}

      {/* 消息列表 */}
      <div className="min-h-0 flex-1 overflow-y-auto py-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-6 pt-16 text-center">
            <div className="flex flex-col gap-1">
              <h1 className="font-serif text-2xl font-bold text-foreground">学习助手</h1>
              <p className="text-[13.5px] text-text-mid">
                用一句话告诉我你想做什么，我来帮你出题、查例题或制定计划
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="rounded-full border border-line-strong bg-sheet px-3 py-1.5 text-xs text-text-mid transition-colors hover:border-muted-foreground hover:text-foreground"
                  onClick={() => send(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-ink text-paper'
                    : msg.role === 'error'
                      ? 'bg-red-50 text-red-700 border border-red-200'
                      : 'bg-sheet border border-line text-foreground'
                }`}
              >
                {msg.role === 'assistant' ? (
                  <div className="prose prose-sm max-w-none
                    prose-headings:font-serif prose-headings:text-foreground
                    prose-p:text-foreground prose-li:text-foreground
                    prose-strong:text-foreground
                    prose-table:w-full prose-table:border-collapse
                    prose-th:border prose-th:border-line prose-th:bg-ink-wash prose-th:px-3 prose-th:py-1.5 prose-th:text-left prose-th:text-[12px]
                    prose-td:border prose-td:border-line prose-td:px-3 prose-td:py-1.5 prose-td:text-[12.5px]">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}

                {/* 开始做题按钮 */}
                {msg.action?.type === 'open_paper' && (
                  <div className="mt-3 border-t border-line pt-3">
                    <Button
                      size="sm"
                      className="text-xs"
                      onClick={() => navigate(`/papers/${msg.action!.paper_id}`)}
                    >
                      开始做题 →
                    </Button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* 思考中动画 */}
          {chatMutation.isPending && (
            <div className="flex justify-start">
              <div className="rounded-2xl border border-line bg-sheet px-4 py-3">
                <span className="inline-flex gap-1">
                  <span className="size-1.5 animate-bounce rounded-full bg-text-mid [animation-delay:0ms]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-text-mid [animation-delay:150ms]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-text-mid [animation-delay:300ms]" />
                </span>
              </div>
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="border-t border-line bg-background pb-4 pt-3">
        <div className="flex items-end gap-2 rounded-xl border-[1.5px] border-ink bg-sheet p-2 shadow-[0_2px_8px_rgba(30,58,95,.08)]">
          <Textarea
            rows={2}
            placeholder="输入你的需求，Enter 发送，Shift+Enter 换行"
            className="min-h-[52px] flex-1 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 text-[13.5px]"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isPending}
          />
          <Button
            type="button"
            disabled={isPending || !input.trim()}
            className="mb-1 shrink-0 px-5 font-bold tracking-[2px]"
            onClick={() => send(input)}
          >
            {chatMutation.isPending ? '思考中…' : '发 送'}
          </Button>
        </div>
      </div>
    </div>
  )
}

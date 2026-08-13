import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getMindmap, updateMindmap } from '@/api/agent'
import { MindmapEditor } from '@/components/mindmap/MindmapEditor'
import { AssistantChat } from '@/components/AssistantChat'
import { Button } from '@/components/ui/button'
import { PATHS } from '@/lib/paths'
import { toastApiError } from '@/lib/errors'
import type { AgentAction } from '@/types/api'

const MINDMAP_SUGGESTIONS = [
  '把"易错点"再展开两条',
  '给"用法"加一个例句分支',
  '整体精简一下',
] as const

/** 思维导图详情：左编辑器（自动保存）+ 右可折叠内嵌助手（对话式改图）。 */
export function MindmapDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const [assistantOpen, setAssistantOpen] = useState(false)
  // 每次进入本页生成一个新的会话 token → 内嵌助手每次都是新对话
  const sessionToken = useMemo(() => Math.random().toString(36).slice(2, 12), [id])

  const query = useQuery({
    queryKey: ['mindmap', id],
    queryFn: () => getMindmap(id),
    enabled: !!id,
  })

  const saveMut = useMutation({
    mutationFn: (outline: string) => updateMindmap(id, { outline_md: outline }),
    onError: toastApiError,
  })

  const onAction = (action: AgentAction) => {
    if (action.type === 'mindmap_updated' && action.mindmap_id === id) {
      qc.invalidateQueries({ queryKey: ['mindmap', id] })
    }
  }

  if (query.isLoading) {
    return <div className="p-4 text-[13.5px] text-muted-ink">加载中…</div>
  }
  if (query.isError || !query.data) {
    return (
      <div className="flex flex-col items-start gap-3 p-4">
        <p className="text-[14px] text-muted-ink">思维导图不存在或已删除</p>
        <Button asChild variant="outline" size="sm"><Link to={PATHS.mindmaps}>返回列表</Link></Button>
      </div>
    )
  }

  const mm = query.data

  return (
    <div className="-mb-12 flex h-[calc(100svh-2.5rem)] w-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <Link to={PATHS.mindmaps} className="font-ui text-[13px] text-quiet hover:text-accent">← 思维导图</Link>
          <span className="truncate text-[16px] font-bold text-ink">{mm.title}</span>
        </div>
        <Button size="sm" variant={assistantOpen ? 'default' : 'outline'}
          onClick={() => setAssistantOpen((v) => !v)}>
          {assistantOpen ? '收起助手' : '🧠 调出助手'}
        </Button>
      </div>

      <div className="flex min-h-0 flex-1 gap-4">
        <div className="min-h-0 flex-1">
          <MindmapEditor
            value={mm.outline_md}
            saving={saveMut.isPending}
            onSave={(outline) => saveMut.mutate(outline)}
          />
        </div>
        {assistantOpen && (
          <div className="flex min-h-0 w-[360px] shrink-0 flex-col rounded-[12px] border border-hairline p-3 max-lg:w-[300px]">
            <AssistantChat
              scope="mindmap"
              mindmapId={id}
              sessionToken={sessionToken}
              storageKey={`agent.chat.mm.${id}.${sessionToken}`}
              onAction={onAction}
              emptyHint="告诉我怎么改这张图，例如："
              suggestions={MINDMAP_SUGGESTIONS}
            />
          </div>
        )}
      </div>
    </div>
  )
}

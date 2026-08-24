import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { PanelGroup, Panel } from 'react-resizable-panels'
import { getMindmap, updateMindmap } from '@/api/agent'
import { useOutlineDraft, OutlineEditor } from '@/components/mindmap/MindmapEditor'
import { MindmapView } from '@/components/mindmap/MindmapView'
import { ResizeHandle } from '@/components/mindmap/ResizeHandle'
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

/** 思维导图详情：Markmap 预览常驻居中，左侧可折叠编辑器（默认隐藏，"编辑"切换）、右侧可折叠内嵌助手。 */
export function MindmapDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const [editorOpen, setEditorOpen] = useState(false)
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
    // 用返回的最新数据回填缓存，保持 ['mindmap', id] 权威、避免自动保存后缓存陈旧
    onSuccess: (data) => qc.setQueryData(['mindmap', id], data),
    onError: toastApiError,
  })

  // hook 必须无条件先于 early return 调用；此时 query 可能尚未就绪，用空串占位，
  // 光标守卫（cur === value）会平滑处理 '' → 真实大纲 的过渡。
  const { draft, onChange } = useOutlineDraft(query.data?.outline_md ?? '', (o) => saveMut.mutate(o))

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
          <Button size="sm" variant={editorOpen ? 'default' : 'outline'}
            onClick={() => setEditorOpen((v) => !v)}>
            {editorOpen ? '收起编辑' : '✏️ 编辑'}
          </Button>
        </div>
        <Button size="sm" variant={assistantOpen ? 'default' : 'outline'}
          onClick={() => setAssistantOpen((v) => !v)}>
          {assistantOpen ? '收起助手' : '🧠 调出助手'}
        </Button>
      </div>

      <PanelGroup direction="horizontal" autoSaveId="mm-workspace" className="flex min-h-0 flex-1">
        {editorOpen && (
          <>
            <Panel id="editor" order={1} defaultSize={30} minSize={20} className="min-h-0 pr-2">
              <OutlineEditor draft={draft} onChange={onChange} saving={saveMut.isPending} />
            </Panel>
            <ResizeHandle />
          </>
        )}

        <Panel id="preview" order={2} minSize={25} className="min-h-0 px-1">
          <div className="h-full rounded-sm border border-hairline bg-card-surface">
            <MindmapView outline={draft} />
          </div>
        </Panel>

        {assistantOpen && (
          <>
            <ResizeHandle />
            <Panel id="assistant" order={3} defaultSize={32} minSize={22} className="min-h-0 pl-2">
              <div className="flex h-full min-h-0 flex-col rounded-sm border border-hairline p-3">
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
            </Panel>
          </>
        )}
      </PanelGroup>
    </div>
  )
}

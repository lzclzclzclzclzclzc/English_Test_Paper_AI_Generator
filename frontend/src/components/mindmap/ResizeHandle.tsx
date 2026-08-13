import { PanelResizeHandle } from 'react-resizable-panels'

/** 面板分隔条：~6px 命中区 + 居中 1px hairline，悬停/拖拽时变宽并染上强调色。 */
export function ResizeHandle() {
  return (
    <PanelResizeHandle className="group relative w-[6px] shrink-0 cursor-col-resize outline-none">
      <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-hairline transition-all group-hover:w-[3px] group-hover:bg-accent group-data-[resize-handle-state=drag]:w-[3px] group-data-[resize-handle-state=drag]:bg-accent" />
    </PanelResizeHandle>
  )
}

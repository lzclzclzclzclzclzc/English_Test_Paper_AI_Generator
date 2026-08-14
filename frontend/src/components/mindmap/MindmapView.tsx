import { useEffect, useRef } from 'react'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'

const transformer = new Transformer()

interface Props {
  /** 大纲 markdown（唯一事实来源） */
  outline: string
  /** 传给 <svg> 的 className；容器需自带宽高 */
  className?: string
}

/** 只读思维导图渲染：markdown 大纲 → Markmap SVG。聊天缩略与详情预览共用。 */
export function MindmapView({ outline, className }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const mmRef = useRef<Markmap | null>(null)

  useEffect(() => {
    if (!svgRef.current) return
    if (!mmRef.current) {
      mmRef.current = Markmap.create(svgRef.current)
    }
    const { root } = transformer.transform(outline || '# ')
    mmRef.current.setData(root)
    mmRef.current.fit()
  }, [outline])

  // 容器尺寸变化（如拖拽分隔条改宽）→ 重新 fit，保持全图可见。
  // rAF 去抖，规避 ResizeObserver loop 警告。
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    let raf = 0
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => mmRef.current?.fit())
    })
    ro.observe(el)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
    }
  }, [])

  useEffect(() => {
    return () => {
      mmRef.current?.destroy()
      mmRef.current = null
    }
  }, [])

  return (
    <svg
      ref={svgRef}
      className={className}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  )
}

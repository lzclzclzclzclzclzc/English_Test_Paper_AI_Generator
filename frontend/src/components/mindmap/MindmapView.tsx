import { useEffect, useRef } from 'react'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'

const transformer = new Transformer()

/** 按层级轮换的品牌色（读 CSS 变量，随浅/深色自动切换）：根=橙红，其后分科色。 */
const BRANCH_VARS = ['--accent', '--grammar', '--listening', '--reading', '--writing', '--success']
function brandColor(node: { state?: { depth?: number } }): string {
  const depth = node.state?.depth ?? 0
  const name = BRANCH_VARS[Math.max(0, depth - 1) % BRANCH_VARS.length] ?? '--accent'
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || '#ef4a2b'
}

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
      mmRef.current = Markmap.create(svgRef.current, { color: brandColor })
    }
    const { root } = transformer.transform(outline || '# ')
    mmRef.current.setData(root)
    mmRef.current.fit()
    // 首帧字体/布局未稳定时 getBBox 偏小，右侧节点会被裁掉；稍后再 fit 一次。
    const t = window.setTimeout(() => mmRef.current?.fit(), 250)
    return () => window.clearTimeout(t)
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

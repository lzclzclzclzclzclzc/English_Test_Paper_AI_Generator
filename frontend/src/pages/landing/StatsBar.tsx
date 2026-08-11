const STATS = [
  { value: '1,428', label: '道中考真题' },
  { value: '10', label: '大中考题型' },
  { value: '56', label: '个知识点全覆盖' },
  { value: '3', label: '档出题强度' },
] as const

/** 数据条:四个赤陶大数字(1,428 题 / 10 题型 / 56 考点 / 3 档强度)。 */
export function StatsBar() {
  return (
    <section className="grid grid-cols-4 gap-8 border-t border-hairline py-[38px] max-sm:grid-cols-2 max-sm:gap-6">
      {STATS.map((s) => (
        <div key={s.label} className="flex flex-col gap-1.5">
          <span className="font-ui text-[32px] font-bold leading-none text-accent tabular-nums">
            {s.value}
          </span>
          <span className="text-[13px] text-quiet">{s.label}</span>
        </div>
      ))}
    </section>
  )
}

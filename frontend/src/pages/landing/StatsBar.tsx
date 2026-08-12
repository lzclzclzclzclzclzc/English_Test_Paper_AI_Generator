const KPIS = [
  { idx: '01', n: '1,428', u: '道', cap: '中考真题' },
  { idx: '02', n: '10', u: '大', cap: '中考题型' },
  { idx: '03', n: '56', u: '个', cap: '知识点全覆盖' },
  { idx: '04', n: '3', u: '档', cap: '出题强度' },
] as const

/** KPI 数据带:四列,编号 + 大号 tabular 数字 + 单位 + 说明。 */
export function StatsBar() {
  return (
    <section className="stats" aria-label="关键数据">
      <div className="l-wrap">
        <div className="stats-grid">
          {KPIS.map((k) => (
            <div className="kpi" key={k.idx}>
              <div className="idx">{k.idx}</div>
              <div className="n num">{k.n}<span className="u">{k.u}</span></div>
              <div className="cap">{k.cap}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

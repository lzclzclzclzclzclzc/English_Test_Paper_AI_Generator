const LOOP_ITEMS = [
  { i: 'A', title: '弱点画像', desc: '每道题都记入 56 个知识点的掌握度，薄弱点一目了然。' },
  { i: 'B', title: '错题本与重练', desc: '错过的题自动进错题本，一键出一份巩固卷。' },
  { i: 'C', title: '弱点复习卷', desc: '根据答题记录算出该补什么，出一份查漏补缺的卷子。' },
] as const

/** #loop 学习闭环:硬边两栏——左判分讲解(callout)+ 右错题沉淀(feat-list)。 */
export function LoopSection() {
  return (
    <section className="section" aria-label="学习闭环">
      <div className="l-wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow-row"><span className="idx">LOOP</span><hr className="hairline" /></div>
            <h2 className="h-sec">交卷之后，<br />学习才真正开始</h2>
          </div>
          <p className="lead">从当场判分到弱点画像，每一次答题都沉淀成可复用的学习资产。</p>
        </div>

        <div className="two-col">
          <div className="col">
            <h3>交卷那一刻，才是开始</h3>
            <p>客观题即交即判，错哪道当场知道。讲解不是标准答案的复读——AI 看得到你写的那个错误答案，讲的是你为什么会错、下次怎么想。</p>
            <div className="callout">
              <span className="x">✕ 你选了 <b>B (has gone)</b></span> → has gone 表示“去了还没回”，而句中 Tom 现在就在上海，应该用 has been in + 时间段来表达一直住到现在……
            </div>
          </div>
          <div className="col">
            <h3>错题不白错</h3>
            <ul className="feat-list">
              {LOOP_ITEMS.map((item) => (
                <li key={item.i}>
                  <div className="ft"><span className="i">{item.i}</span> {item.title}</div>
                  <p>{item.desc}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}

const FAQS = [
  {
    qi: 'Q1',
    q: '题目是哪里来的？',
    a: '来自上海中考一模、二模真题书及听力/阅读/作文素材，经章节切分、知识点归并、人工审核入库，每道题都保留题源与考点标注，共 1,428 道。',
  },
  {
    qi: 'Q2',
    q: 'AI 会不会瞎出题？',
    a: '选『AI 改编』或『全新原创』时引擎会换词、换语境甚至从零命题，同一考点每次都是新题；选『真题原样』则忠实还原，题目右上角永远标明出身。',
  },
] as const

/** #faq 常见问题:左右栏列表(Q 编号 + 问 / 答)。 */
export function FaqSection() {
  return (
    <section className="section" id="faq">
      <div className="l-wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow-row"><span className="idx">FAQ</span><hr className="hairline" /></div>
            <h2 className="h-sec">常见问题</h2>
          </div>
          <p className="lead">关于题源与 AI 出题的两个高频问题。</p>
        </div>

        <div className="faq-list">
          {FAQS.map((f) => (
            <div className="faq-item" key={f.qi}>
              <div className="q"><span className="qi">{f.qi}</span><span>{f.q}</span></div>
              <div className="a">{f.a}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

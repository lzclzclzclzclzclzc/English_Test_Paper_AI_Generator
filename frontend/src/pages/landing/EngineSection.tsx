const STEPS = [
  { sn: '01', se: 'Parser · 解析要求', st: '读懂你的一句话', p: '把你的一句话读成题型、考点、题量与出题强度，不用填任何表单。' },
  { sn: '02', se: 'Retriever · 检索真题', st: '先找真题再动手', p: '从 1,428 道真实中考题里硬过滤 + 向量召回，命中最贴合的候选——先有真题，AI 才动手，不是凭空生成。' },
  { sn: '03', se: 'Reviser · 改编校验', st: '按强度改编把关', p: '按强度保留原题、轻改或全新命题，每道都过校验——校验不过自动回落，不出怪题。' },
  { sn: '04', se: 'Assemble · 成卷判分', st: '即出即做当场判', p: '组卷落库即出即做，客观题交卷当场判分。' },
] as const

const WAYS = [
  { wt: '真题原样', b: 'Original', p: '一模二模考过什么就练什么，题源、考点都有出处。' },
  { wt: 'AI 改编', b: 'Revised', p: '换词换语境、考点不变，题库再厚也不给你做重复卷。' },
  { wt: '全新原创', b: 'Original AI', p: '指定主题也可以：『出一套关于环保的完形填空』，AI 从零命题、自动校验。' },
] as const

/** #engine 引擎:四步网格 +「三种练法」三卡 + 脚注。 */
export function EngineSection() {
  return (
    <section className="section" id="engine">
      <div className="l-wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow-row"><span className="idx">ENGINE</span><hr className="hairline" /></div>
            <h2 className="h-sec">一句话，<br />四步变成一份卷子</h2>
          </div>
          <p className="lead">从读懂你的需求到成卷判分，出题引擎四步走完——真题在先，AI 才动手。</p>
        </div>

        <div className="steps">
          {STEPS.map((s) => (
            <div className="step" key={s.sn}>
              <div className="sn num">{s.sn}</div>
              <span className="se">{s.se}</span>
              <div className="st">{s.st}</div>
              <p>{s.p}</p>
            </div>
          ))}
        </div>

        <div className="three-ways">
          <h3 className="tw-head">同一个考点，三种练法</h3>
          <div className="ways-grid">
            {WAYS.map((w) => (
              <div className="way" key={w.b}>
                <div className="wt">{w.wt} <span className="b">{w.b}</span></div>
                <p>{w.p}</p>
              </div>
            ))}
          </div>
          <p className="ways-foot">每道题右上角都标着它的出身——原题、轻改还是新出，一眼可查。</p>
        </div>
      </div>
    </section>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { PATHS } from '@/lib/paths'
import { FREE_GENERATE_PER_DAY } from '@/lib/quota'
import { scrollToAnchor } from './shared'

/* ── HeroDemo 数据:多条示例循环,覆盖语法/听力两族与原题/轻改两种出身 ── */

interface DemoLine {
  num: string
  type: string
  tier: 'orig' | 'edit'
  stem: React.ReactNode
}
interface DemoCase {
  query: string
  meta: string
  lines: DemoLine[]
}

const DEMO_CASES: readonly DemoCase[] = [
  {
    query: '来 12 道现在完成时的单项选择，再配 3 道听力填词',
    meta: '15 题 · 语法 12 / 听力 3',
    lines: [
      { num: '01', type: '单项选择', tier: 'orig', stem: <>Tom <b>___</b> in Shanghai since 2019.</> },
      { num: '02', type: '单项选择', tier: 'edit', stem: <>She <b>___</b> the film twice with her friends.</> },
      { num: '13', type: '听力填词', tier: 'orig', stem: <>The train to Nanjing leaves at <b>___</b>.</> },
      { num: '14', type: '听力填词', tier: 'edit', stem: <>Mike has lived there for <b>___</b> years.</> },
    ],
  },
  {
    query: '出一套关于环保的完形填空，全新原创',
    meta: '1 篇 · 阅读 6',
    lines: [
      { num: '01', type: '完形填空', tier: 'edit', stem: <>Our city has started a new <b>___</b> program.</> },
      { num: '02', type: '完形填空', tier: 'edit', stem: <>Instead of driving, more people <b>___</b> to work.</> },
      { num: '03', type: '完形填空', tier: 'edit', stem: <>Small changes can make a big <b>___</b>.</> },
    ],
  },
  {
    query: '句子改写 5 道，再来一篇阅读理解',
    meta: '9 题 · 语法 5 / 阅读 4',
    lines: [
      { num: '01', type: '句子改写', tier: 'orig', stem: <>He cleans the classroom every day. (改为被动语态)</> },
      { num: '02', type: '句子改写', tier: 'edit', stem: <>The news is so exciting. (改为感叹句)</> },
      { num: '06', type: '阅读理解', tier: 'orig', stem: <>What is the main idea of the passage?</> },
    ],
  },
]

type Phase = 'typing' | 'checking' | 'results' | 'leaving'
const TYPE_MS = 70
const TYPE_DONE_PAUSE_MS = 350
const CHECKING_MS = 800
const HOLD_MS = 5000
const FADE_MS = 300

/** variant-5「出卷示意」面板:保留打字机状态机,外壳换成 SaaS 卡片样式。 */
function HeroDemo() {
  const reduced = useMemo(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  )
  const [caseIdx, setCaseIdx] = useState(0)
  const [typed, setTyped] = useState(0)
  const [phase, setPhase] = useState<Phase>('typing')

  const demo = DEMO_CASES[caseIdx] ?? DEMO_CASES[0]!

  useEffect(() => {
    if (reduced) return
    if (phase === 'typing') {
      if (typed < demo.query.length) {
        const t = setTimeout(() => setTyped((n) => n + 1), TYPE_MS)
        return () => clearTimeout(t)
      }
      const t = setTimeout(() => setPhase('checking'), TYPE_DONE_PAUSE_MS)
      return () => clearTimeout(t)
    }
    if (phase === 'checking') {
      const t = setTimeout(() => setPhase('results'), CHECKING_MS)
      return () => clearTimeout(t)
    }
    if (phase === 'results') {
      const t = setTimeout(() => setPhase('leaving'), HOLD_MS)
      return () => clearTimeout(t)
    }
    const t = setTimeout(() => {
      setCaseIdx((i) => (i + 1) % DEMO_CASES.length)
      setTyped(0)
      setPhase('typing')
    }, FADE_MS)
    return () => clearTimeout(t)
  }, [phase, typed, reduced, demo.query.length])

  const shownQuery = reduced ? demo.query : demo.query.slice(0, typed)
  const showCaret = !reduced && (phase === 'typing' || phase === 'checking')
  const showChecking = !reduced && phase === 'checking'
  const showResults = reduced || phase === 'results' || phase === 'leaving'

  return (
    <aside className="demo" aria-hidden>
      <div className="demo-top">
        <span className="k">GENERATE · 自然语言出卷</span>
        <span className="dots"><i className="on" /><i /><i /></span>
      </div>
      <div className="prompt">
        <div className="lbl">Prompt · 输入示例</div>
        <div className="txt">
          {shownQuery}
          {showCaret && <span className="caret" />}
        </div>
      </div>
      {showChecking && (
        <div className="status">
          <span className="pulse" />
          <span className="stxt">检索题库 · 校验中</span>
        </div>
      )}
      <div
        style={{ transition: 'opacity .3s ease', opacity: phase === 'leaving' ? 0 : 1 }}
      >
        {showResults && (
          <>
            <div className="paper-head">
              <span className="t">PAPER</span>
              <span className="meta num">{demo.meta}</span>
            </div>
            <div className="rows">
              {demo.lines.map((line) => (
                <div className="qrow" key={line.num}>
                  <div className="qno num">{line.num}</div>
                  <div className="qbody">
                    <div className="qtags">
                      <span className="tag tag--type">{line.type}</span>
                      <span className={`tag ${line.tier === 'orig' ? 'tag--orig' : 'tag--edit'}`}>
                        {line.tier === 'orig' ? '原题' : '轻改'}
                      </span>
                    </div>
                    <div className="stem">{line.stem}</div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </aside>
  )
}

/** Hero:深色首屏,左文案双 CTA,右 HeroDemo「出卷示意」面板。 */
export function HeroSection() {
  return (
    <section className="hero">
      <div className="l-wrap">
        <div className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">真题库 + AI 引擎 · 上海中考英语 · 十大题型</p>
            <h1>说一句你想练什么，<br />出一份能直接做的卷子</h1>
            <p className="sub">
              题目全部来自上海中考一模二模真题——<span style={{ color: '#fff' }}>每道题都有真题出处、标注考点，不是 AI 凭空编造</span>。配上能听懂你需求的出题引擎：单选、词形、句改、听力、阅读、完形、作文十大真实题型，覆盖 56 个中考考点，按需几秒组成一份即出即做的卷子——做完当场判分、逐题讲解、记入你的掌握度。
            </p>
            <div className="cta-row">
              <Link to={PATHS.login} className="btn btn--primary btn--lg">免费出一份卷子</Link>
              <a href="#pricing" onClick={(e) => scrollToAnchor(e, 'pricing')} className="btn btn--ghost-dark btn--lg">看看定价 ↓</a>
            </div>
            <p className="fineprint">
              免费注册即可使用<span className="dot">·</span>每天 {FREE_GENERATE_PER_DAY} 次出卷额度<span className="dot">·</span>无需付费开始
            </p>
          </div>
          <HeroDemo />
        </div>
      </div>
    </section>
  )
}

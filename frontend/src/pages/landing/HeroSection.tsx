import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FAMILY_CHIP_CLASS, TYPE_FAMILY, TYPE_LABELS } from '@/lib/kp'
import { PATHS } from '@/lib/paths'
import { FREE_GENERATE_PER_DAY } from '@/lib/quota'
import { scrollToAnchor, TIER_CHIP_CLASS, TIER_LABELS, type RevisionTier } from './shared'

/* ── HeroDemo 数据:2-3 条示例循环,覆盖语法/听力/阅读三族与三档出身 ── */

interface DemoLine {
  num: string
  typeId: string
  tier: RevisionTier
  stem: string
}

interface DemoCase {
  query: string
  header: string
  lines: DemoLine[]
}

const DEMO_CASES: readonly DemoCase[] = [
  {
    query: '来 12 道现在完成时的单项选择,再配 3 道听力填词',
    header: 'PAPER · 15 题 · 语法 12 / 听力 3',
    lines: [
      { num: '01', typeId: 'single_choice', tier: 'original', stem: 'Tom ___ in Shanghai since 2019.' },
      { num: '02', typeId: 'single_choice', tier: 'light', stem: 'She ___ the film twice with her friends.' },
      { num: '13', typeId: 'listening_fill_blank', tier: 'original', stem: 'The train to Nanjing leaves at ___.' },
      { num: '14', typeId: 'listening_fill_blank', tier: 'light', stem: 'Mike has lived there for ___ years.' },
    ],
  },
  {
    query: '出一套关于环保的完形填空,全新原创',
    header: 'PAPER · 1 篇 · 阅读 6',
    lines: [
      { num: '01', typeId: 'cloze_single_choice', tier: 'fresh', stem: 'Our city has started a new ___ program.' },
      { num: '02', typeId: 'cloze_single_choice', tier: 'fresh', stem: 'Instead of driving, more people ___ to work.' },
      { num: '03', typeId: 'cloze_single_choice', tier: 'fresh', stem: 'Small changes can make a big ___.' },
    ],
  },
  {
    query: '句子改写 5 道,再来一篇阅读理解',
    header: 'PAPER · 9 题 · 语法 5 / 阅读 4',
    lines: [
      { num: '01', typeId: 'sentence_rewriting', tier: 'original', stem: 'He cleans the classroom every day. (改为被动语态)' },
      { num: '02', typeId: 'sentence_rewriting', tier: 'light', stem: 'The news is so exciting. (改为感叹句)' },
      { num: '06', typeId: 'reading_longtext_single_choice', tier: 'original', stem: 'What is the main idea of the passage?' },
    ],
  },
]

/* ── 打字机状态机:typing → checking → results(hold)→ leaving → 下一条 ── */

type Phase = 'typing' | 'checking' | 'results' | 'leaving'

const TYPE_MS = 70
const TYPE_DONE_PAUSE_MS = 350
const CHECKING_MS = 800
const HOLD_MS = 5000
const FADE_MS = 300

const CHIP = 'shrink-0 rounded-sm border px-2 py-0.5 font-ui text-[11px] font-[550]'

/**
 * 自然语言出卷的拟真演示面板。所有定时器都由 useEffect 返回清理;
 * prefers-reduced-motion 时不打字不循环,直接静态显示第一条的完成态。
 */
function HeroDemo() {
  // 挂载时读一次即可:营销页停留短,不监听运行中切换
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
    // leaving:淡出后切下一条并复位
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
    <div aria-hidden className="rounded-md border border-hairline p-6">
      <p className="font-ui text-[11px] font-bold tracking-[0.1em] text-accent">
        GENERATE · 自然语言出卷
      </p>
      <div
        className={`transition-opacity duration-300 ${phase === 'leaving' ? 'opacity-0' : 'opacity-100'}`}
      >
        {/* 「输入框」:逐字打出的示例 query + 赤陶闪烁光标 */}
        <div className="mt-4 min-h-[80px] rounded-[3px] border border-ink-20 px-4 py-3 text-[15px] leading-[1.8] text-ink">
          {shownQuery}
          {showCaret && (
            <span className="kk-caret ml-0.5 inline-block h-[1em] w-[2px] translate-y-[0.15em] bg-accent" />
          )}
        </div>
        {/* 状态行:定高防跳动 */}
        <div className="mt-3 flex h-5 items-center gap-2">
          {showChecking && (
            <>
              <span className="kk-pulse size-2 rounded-full bg-accent" />
              <span className="font-ui text-[13px] text-quiet">检索题库 · 校验中</span>
            </>
          )}
        </div>
        {/* 结果区:卷头行 + 题目行,kk-rise 错峰浮现 */}
        <div className="mt-3 min-h-[176px] border-t border-hairline pt-4">
          {showResults && (
            <div key={caseIdx}>
              <p
                className="kk-rise font-mono text-[12px] text-quiet"
                style={{ animationFillMode: 'backwards' }}
              >
                {demo.header}
              </p>
              {demo.lines.map((line, i) => {
                const family = TYPE_FAMILY[line.typeId]
                return (
                  <div
                    key={line.num}
                    className="kk-rise mt-3 flex min-w-0 items-center gap-2"
                    style={{ animationDelay: `${(i + 1) * 90}ms`, animationFillMode: 'backwards' }}
                  >
                    <span className="w-6 shrink-0 font-mono text-[12px] text-quiet">{line.num}</span>
                    <span className={`${CHIP} ${family ? FAMILY_CHIP_CLASS[family] : ''}`}>
                      {TYPE_LABELS[line.typeId] ?? line.typeId}
                    </span>
                    <span className={`${CHIP} ${TIER_CHIP_CLASS[line.tier]}`}>
                      {TIER_LABELS[line.tier]}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[14px] text-muted-ink">
                      {line.stem}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** Hero:左文案 + 双 CTA,右 HeroDemo 打字机演示面板。 */
export function HeroSection() {
  return (
    <section className="grid grid-cols-[1.1fr_1fr] gap-[72px] pb-[80px] pt-[96px] max-md:grid-cols-1 max-md:gap-12 max-md:pb-14 max-md:pt-14">
      <div>
        <p className="font-ui text-[12px] tracking-[0.1em] text-accent">
          真题库 + AI 引擎 · 上海中考英语 · 九大题型
        </p>
        <h1 className="mt-6 text-[58px] font-normal leading-[1.32] text-ink [font-family:var(--font-display)] max-md:text-[36px]">
          说一句你想练什么，<mark>出一份能直接做的卷子</mark>
        </h1>
        <p className="mt-8 max-w-[42rem] text-[16px] leading-[1.9] text-muted-ink">
          从上海一模二模真题书里建起的题库，配上能听懂你需求的出题引擎：单选、词形、句改、听力、阅读九大题型，按考点几秒组成一份即出即做的卷子——做完当场判分、逐题讲解、记入你的掌握度。
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <Link
            to={PATHS.login}
            className="rounded-sm border border-accent bg-wash px-7 py-3 font-ui text-[15px] tracking-[0.05em] text-ink transition-colors hover:text-accent"
          >
            免费出一份卷子
          </Link>
          <a
            href="#pricing"
            onClick={(e) => scrollToAnchor(e, 'pricing')}
            className="rounded-sm border border-hairline px-6 py-3 font-ui text-[15px] text-muted-ink transition-colors hover:border-accent hover:bg-tint hover:text-accent"
          >
            看看定价 ↓
          </a>
        </div>
        <p className="mt-5 text-[13px] text-quiet">
          免费注册即可使用，每天 {FREE_GENERATE_PER_DAY} 次出卷额度，无需付费开始
        </p>
      </div>
      <HeroDemo />
    </section>
  )
}

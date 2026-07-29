import { Link } from 'react-router-dom'

const STATS = [
  { value: '4,180', label: '题库题量' },
  { value: '3', label: '类题型' },
  { value: '6', label: '秒生成' },
  { value: '26', label: '知识点' },
] as const

const HOW_STEPS = [
  { num: '01 · PARSER', title: '解析要求', desc: '把你的一句话解析成题型、考点、题量、难度和改题力度。' },
  { num: '02 · RETRIEVER', title: '检索题库', desc: '硬过滤 + 向量召回，从真题库中命中最贴合的候选题。' },
  { num: '03 · REVISER', title: '改题加工', desc: '按力度保留原题、轻度改写或全新出题，校验不过自动回落。' },
  { num: '04 · ASSEMBLE', title: '成卷落库', desc: '组卷计分、落库出 paper_id，随时开卷、判分、复盘。' },
] as const

const MODES = [
  { code: 'FRESH', name: '新生成', desc: '按你的描述从题库出一份全新的卷子。' },
  { code: 'REMEDIATION', name: '错题巩固', desc: '围绕错题本里选中的题目，定向出巩固练习。' },
  { code: 'REVIEW', name: '综合复习', desc: '根据答题记录算出薄弱考点，出查漏补缺的复习卷。' },
] as const

const BANK_CHIPS = [
  'EPUB→md',
  '章节切分',
  '知识点树归并',
  '人工审核',
  '结构化抽题',
  '双写入库',
] as const

/** 对外落地页（handoff 第 1 屏）：粘顶页眉 + hero + 数据条 + 流程 / 模式 / 题库三段。 */
export function LandingPage() {
  return (
    <div className="min-h-svh bg-background">
      {/* 粘顶页眉：磨砂底 + 下细线，无阴影 */}
      <header
        className="sticky top-0 z-10 border-b border-hairline"
        style={{
          backdropFilter: 'saturate(1.4) blur(8px)',
          background: 'color-mix(in oklab, var(--surface-page) 88%, transparent)',
        }}
      >
        <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between px-14 max-md:px-6">
          <span className="text-[21px] tracking-[0.06em] text-ink [font-family:var(--font-display)]">
            中考英语 AI 试卷生成器
          </span>
          <nav className="flex items-center gap-6">
            <a href="#how" className="text-[14px] text-muted-ink transition-colors hover:text-accent max-sm:hidden">
              流程
            </a>
            <a href="#engine" className="text-[14px] text-muted-ink transition-colors hover:text-accent max-sm:hidden">
              模式
            </a>
            <a href="#bank" className="text-[14px] text-muted-ink transition-colors hover:text-accent max-sm:hidden">
              题库
            </a>
            <Link
              to="/login"
              className="rounded-sm border border-accent bg-wash px-4 py-1.5 text-[14px] text-ink transition-colors hover:text-accent"
            >
              进入 →
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-[1180px] px-14 max-md:px-6">
        {/* Hero：居左不居中，唯一 CTA */}
        <section className="pb-[88px] pt-[120px]">
          <p className="text-[12px] tracking-[0.1em] text-accent">
            RAG + 大模型 · 中考英语 · 纯文字题型
          </p>
          <h1 className="mt-6 max-w-[16em] text-[58px] font-normal leading-[1.32] text-ink [font-family:var(--font-display)] max-md:text-[36px]">
            说一句你想练什么，<mark>出一份能直接做的卷子</mark>
          </h1>
          <p className="mt-8 max-w-[42rem] text-[16px] leading-[1.9] text-muted-ink">
            从真题书里建起的结构化题库，加上会解析你需求的 AI
            引擎：选择题、词形转换、句子改写，按考点和难度组一份即出即做的中考英语卷，做完当场判分、讲解、记录掌握度。
          </p>
          <div className="mt-10">
            <Link
              to="/login"
              className="inline-block rounded-sm border border-accent bg-wash px-8 py-[13px] text-[16px] tracking-[0.05em] text-ink transition-colors hover:text-accent"
            >
              开始生成试卷
            </Link>
          </div>
        </section>

        {/* 数据条 */}
        <section className="grid grid-cols-4 gap-8 border-t border-hairline py-[38px] max-sm:grid-cols-2">
          {STATS.map((s) => (
            <div key={s.label} className="flex flex-col gap-1">
              <span className="text-[32px] leading-none text-accent">{s.value}</span>
              <span className="text-[13px] text-quiet">{s.label}</span>
            </div>
          ))}
        </section>

        {/* #how 生成流程 */}
        <section id="how" className="scroll-mt-20 py-14">
          <div className="grid grid-cols-4 divide-x divide-ink-10 border-t border-accent max-md:grid-cols-2 max-md:divide-x-0">
            {HOW_STEPS.map((step) => (
              <div key={step.num} className="flex flex-col gap-3 py-8 pr-6 [&:not(:first-child)]:pl-6 max-md:pl-0">
                <span className="text-[11px] tracking-[0.1em] text-accent">{step.num}</span>
                <span className="text-[18px] text-ink">{step.title}</span>
                <p className="text-[14px] leading-[1.8] text-muted-ink">{step.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* #engine 模式与判分 */}
        <section id="engine" className="grid scroll-mt-20 grid-cols-2 gap-[72px] py-14 max-md:grid-cols-1">
          <div>
            <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">三种模式</h2>
            <div className="mt-4">
              {MODES.map((m) => (
                <div key={m.code} className="flex gap-5 border-t border-hairline py-[22px] last:border-b">
                  <span className="min-w-[88px] pt-1 text-[12px] tracking-[0.1em] text-accent">
                    {m.code}
                  </span>
                  <div>
                    <div className="text-[17px] text-ink">{m.name}</div>
                    <p className="mt-2 text-[14px] leading-[1.8] text-muted-ink">{m.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">判分规则</h2>
            <p className="mt-4 max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
              客观题即交即判：单选对答案，填空与改写忽略大小写与句末标点，一题一空逐空比对。判分结果连同解析入口一起返回。
            </p>
            <pre className="mt-6 overflow-x-auto rounded-md border border-hairline p-5 font-mono text-[13px] leading-[1.8] text-muted-ink">
{`grade("A", answer="A")          → `}<mark>true</mark>{`
grade("looked ", "looked.")     → `}<mark>true</mark>{`
grade("Looked", "looked")       → `}<mark>true</mark>{`
grade("look",   "looked")       → false`}
            </pre>
          </div>
        </section>

        {/* #bank 题库 */}
        <section id="bank" className="scroll-mt-20 py-14">
          <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">从真题书长出来的题库</h2>
          <p className="mt-4 max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
            题库不是爬来的：真题书经过六道工序进库，知识点树由人工审核后才生效，每道题都带题源、考点与难度。
          </p>
          <div className="mt-6 flex flex-wrap gap-2.5">
            {BANK_CHIPS.map((chip) => (
              <span
                key={chip}
                className={
                  chip === '人工审核'
                    ? 'rounded-sm border border-accent bg-wash px-3 py-1.5 text-[13px] text-ink'
                    : 'rounded-sm border border-hairline px-3 py-1.5 text-[13px] text-muted-ink'
                }
              >
                {chip}
              </span>
            ))}
          </div>
          <div className="mt-14 flex flex-wrap items-center justify-between gap-4 border-t border-hairline pb-20 pt-8">
            <p className="text-[15px] text-muted-ink">出一份卷子，看看 AI 有多懂中考英语。</p>
            <Link
              to="/login"
              className="rounded-sm border border-accent bg-wash px-6 py-2.5 text-[15px] text-ink transition-colors hover:text-accent"
            >
              开始使用 →
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}

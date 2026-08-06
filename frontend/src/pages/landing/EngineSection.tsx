import { TIER_CHIP_CLASS, TIER_LABELS, type RevisionTier } from './shared'

const STEPS = [
  {
    num: '01 · PARSER',
    title: '解析要求',
    desc: '把你的一句话读成题型、考点、题量与出题强度，不用填任何表单。',
  },
  {
    num: '02 · RETRIEVER',
    title: '检索真题',
    desc: '硬过滤 + 向量召回，从 1,397 道真题里命中最贴合的候选题。',
  },
  {
    num: '03 · REVISER',
    title: '改编校验',
    desc: '按强度保留原题、轻改或全新命题，每道都过校验——校验不过自动回落，不出怪题。',
  },
  {
    num: '04 · ASSEMBLE',
    title: '成卷判分',
    desc: '组卷落库即出即做，客观题交卷当场判分。',
  },
] as const

const TIERS: { tier: RevisionTier; name: string; desc: string }[] = [
  { tier: 'original', name: '真题原样', desc: '一模二模考过什么就练什么，题源、考点都有出处。' },
  { tier: 'light', name: 'AI 改编', desc: '换词换语境、考点不变，题库再厚也不给你做重复卷。' },
  {
    tier: 'fresh',
    name: '全新原创',
    desc: '指定主题也可以：『出一套关于环保的完形填空』，AI 从零命题、自动校验。',
  },
]

/** #engine 引擎:上段四步流程(四列 divide-x),下段三档出题强度细线列表。 */
export function EngineSection() {
  return (
    <section id="engine" className="scroll-mt-20 border-t border-hairline py-14">
      <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">
        一句话，四步变成一份卷子
      </h2>
      <div className="mt-8 grid grid-cols-4 divide-x divide-ink-10 border-t border-accent max-md:grid-cols-2 max-md:divide-x-0">
        {STEPS.map((step) => (
          <div
            key={step.num}
            className="flex flex-col gap-3 py-8 pr-6 [&:not(:first-child)]:pl-6 max-md:pl-0"
          >
            <span className="text-[11px] tracking-[0.1em] text-accent">{step.num}</span>
            <span className="text-[18px] text-ink">{step.title}</span>
            <p className="text-[14px] leading-[1.8] text-muted-ink">{step.desc}</p>
          </div>
        ))}
      </div>

      <h3 className="mt-12 text-[19px] text-ink">同一个考点，三种练法</h3>
      <div className="mt-4">
        {TIERS.map((t) => (
          <div key={t.tier} className="flex gap-5 border-t border-hairline py-[22px] last:border-b">
            <span
              className={`h-fit shrink-0 rounded-sm border px-2.5 py-1 font-ui text-[12px] font-[550] ${TIER_CHIP_CLASS[t.tier]}`}
            >
              {TIER_LABELS[t.tier]}
            </span>
            <div>
              <div className="text-[17px] text-ink">{t.name}</div>
              <p className="mt-2 max-w-[42rem] text-[14px] leading-[1.8] text-muted-ink">{t.desc}</p>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-6 text-[15px] leading-[1.9] text-muted-ink">
        每道题右上角都标着它的出身——原题、轻改还是新出，一眼可查。
      </p>
    </section>
  )
}

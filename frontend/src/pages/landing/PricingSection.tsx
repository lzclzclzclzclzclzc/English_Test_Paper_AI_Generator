import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { formatYuan } from '@/lib/money'
import { PATHS } from '@/lib/paths'
import { BENEFITS, FREE_TIER_SUMMARY, PRICING_PLANS } from '@/lib/pricing'

interface PricingColumn {
  key: string
  name: string
  price: string
  suffix: string
  note?: string
  line: string
  recommended: boolean
}

const PLAN_LINES: Record<string, string> = {
  monthly: '全部功能不限量',
  quarterly: '全部功能不限量',
  yearly: '一年安心用到考前',
}

/* 免费列 + PRICING_PLANS 三档,共四列。 */
const COLUMNS: readonly PricingColumn[] = [
  {
    key: 'free',
    name: '免费',
    price: '¥0',
    suffix: '永久',
    line: FREE_TIER_SUMMARY,
    recommended: false,
  },
  ...PRICING_PLANS.map((plan) => ({
    key: plan.id,
    name: plan.name,
    price: formatYuan(plan.amountCents),
    suffix: `/${plan.durationDays} 天`,
    note: plan.perMonthNote,
    line: PLAN_LINES[plan.id] ?? '全部功能不限量',
    recommended: plan.recommended === true,
  })),
]

/* 四列分隔线:桌面 divide-x 效果;max-md 2×2 时行首列去左线;max-sm 单列全去。 */
const CELL_BORDERS = [
  '',
  'border-l border-l-ink-10 max-sm:border-l-0',
  'border-l border-l-ink-10 max-md:border-l-0',
  'border-l border-l-ink-10 max-sm:border-l-0',
] as const

const CTA_PRIMARY =
  'inline-block rounded-sm border border-accent bg-wash px-4 py-2 font-ui text-[13.5px] text-ink transition-colors hover:text-accent'
const CTA_SECONDARY =
  'inline-block rounded-sm border border-hairline px-4 py-2 font-ui text-[13.5px] text-muted-ink transition-colors hover:border-accent hover:bg-tint hover:text-accent'

/** #pricing 定价:免费 + 三档会员四列 hairline 分栏 + BENEFITS 权益表。 */
export function PricingSection() {
  const { data: user } = useAuth()
  const loggedIn = Boolean(user)

  const ctaFor = (key: string): { label: string; to: string } => {
    if (loggedIn) {
      return key === 'free'
        ? { label: '进入工作台 →', to: PATHS.home }
        : { label: '去开通会员 →', to: PATHS.membership }
    }
    return key === 'free'
      ? { label: '免费开始', to: PATHS.login }
      : { label: '注册后开通', to: PATHS.login }
  }

  return (
    <section id="pricing" className="scroll-mt-20 border-t border-hairline py-14">
      <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">定价</h2>
      <p className="mt-3 max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
        免费额度每天刷新，会员按需开通——先用免费额度出一份卷子，再决定要不要付费。
      </p>

      <div className="mt-8 grid grid-cols-4 border-b border-hairline max-md:grid-cols-2 max-sm:grid-cols-1">
        {COLUMNS.map((col, i) => {
          const cta = ctaFor(col.key)
          return (
            <div
              key={col.key}
              className={`flex flex-col gap-3 border-t px-7 py-7 first:pl-0 max-md:[&:nth-child(odd)]:pl-0 max-sm:px-0 ${
                col.recommended ? 'border-t-accent' : 'border-t-hairline'
              } ${CELL_BORDERS[i] ?? ''}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[15px] text-ink">{col.name}</span>
                {col.recommended && (
                  <span className="rounded-sm border border-accent bg-wash px-1.5 py-0.5 font-ui text-[11px] text-ink">
                    推荐
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="font-ui text-[28px] font-[650] leading-none text-accent tabular-nums">
                  {col.price}
                </span>
                <span className="text-[13px] text-quiet">{col.suffix}</span>
              </div>
              <span className="min-h-[1.2em] text-[12.5px] text-quiet">{col.note ?? ''}</span>
              <p className="text-[13.5px] leading-[1.8] text-muted-ink">{col.line}</p>
              <div className="mt-auto pt-2">
                <Link to={cta.to} className={col.recommended ? CTA_PRIMARY : CTA_SECONDARY}>
                  {cta.label}
                </Link>
              </div>
            </div>
          )
        })}
      </div>

      {/* 权益表:版式同会员页 */}
      <div className="mt-10 max-w-[42rem]">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="border-b border-ink-20 text-left">
              <th className="py-2.5 pr-4 text-[11px] font-bold tracking-[0.1em] text-quiet">
                功能
              </th>
              <th className="w-28 py-2.5 text-center text-[11px] font-bold tracking-[0.1em] text-quiet">
                免费
              </th>
              <th className="w-28 py-2.5 text-center text-[11px] font-bold tracking-[0.1em] text-accent">
                会员
              </th>
            </tr>
          </thead>
          <tbody>
            {BENEFITS.map((b) => (
              <tr key={b.feature} className="border-b border-hairline transition-colors hover:bg-tint">
                <td className="py-2.5 pr-4 text-ink">{b.feature}</td>
                <td className="py-2.5 text-center text-muted-ink">{b.free}</td>
                <td className="py-2.5 text-center text-ink">{b.member}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-4 text-[12px] text-quiet">到期不自动续费；续费从当前有效期顺延。</p>
      </div>
    </section>
  )
}

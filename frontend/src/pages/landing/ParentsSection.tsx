import { formatYuan } from '@/lib/money'
import { PRICING_PLANS } from '@/lib/pricing'

const monthly = PRICING_PLANS.find((p) => p.id === 'monthly')
const monthlyPrice = monthly ? formatYuan(monthly.amountCents) : '¥9.9'

const POINTS = [
  {
    title: '题目有出处',
    desc: '全部题源来自上海一模二模真题书，经人工审核入库，不是网上爬的题。',
  },
  {
    title: '进步看得见',
    desc: '掌握度页按知识点统计孩子的强弱变化，练没练、进步没进步，打开就知道。',
  },
  {
    title: '价格先说清',
    desc: `免费额度每天都有，会员月付 ${monthlyPrice}，不自动续费、不藏收费项。`,
  },
] as const

/** #parents 给家长的三句话:引言 + 三列(出处 / 进步 / 价格)。 */
export function ParentsSection() {
  return (
    <section id="parents" className="scroll-mt-20 border-t border-hairline py-14">
      <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">
        给家长的三句话
      </h2>
      <p className="mt-3 max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
        孩子在这里做的每一份卷子、错的每一道题，都沉淀成看得见的记录。
      </p>
      <div className="mt-8 grid grid-cols-3 gap-10 max-md:grid-cols-1 max-md:gap-6">
        {POINTS.map((p) => (
          <div key={p.title}>
            <div className="text-[17px] text-ink">{p.title}</div>
            <p className="mt-2 text-[14px] leading-[1.8] text-muted-ink">{p.desc}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

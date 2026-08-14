import { formatYuan } from '@/lib/money'
import { PRICING_PLANS } from '@/lib/pricing'

const monthly = PRICING_PLANS.find((p) => p.id === 'monthly')
const monthlyPrice = monthly ? formatYuan(monthly.amountCents) : '¥9.9'

const POINTS = [
  { pi: '01 · Source', title: '题目有出处', desc: '全部题源来自上海一模二模真题书，经人工审核入库，不是网上爬的题。' },
  { pi: '02 · Progress', title: '进步看得见', desc: '掌握度页按知识点统计孩子的强弱变化，练没练、进步没进步，打开就知道。' },
  { pi: '03 · Price', title: '价格先说清', desc: `免费额度每天都有，会员月付 ${monthlyPrice}，不自动续费、不藏收费项。` },
] as const

/** #parents 给家长的三句话:三卡顶边。 */
export function ParentsSection() {
  return (
    <section className="section" aria-label="给家长">
      <div className="l-wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow-row"><span className="idx">PARENTS</span><hr className="hairline" /></div>
            <h2 className="h-sec">给家长的<br />三句话</h2>
          </div>
          <p className="lead">孩子在这里做的每一份卷子、错的每一道题，都沉淀成看得见的记录。</p>
        </div>

        <div className="parents-grid">
          {POINTS.map((p) => (
            <div className="pcard" key={p.pi}>
              <div className="pi">{p.pi}</div>
              <h4>{p.title}</h4>
              <p>{p.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

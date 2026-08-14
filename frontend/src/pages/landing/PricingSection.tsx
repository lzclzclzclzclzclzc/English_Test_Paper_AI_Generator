import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { formatYuan } from '@/lib/money'
import { PATHS } from '@/lib/paths'
import { BENEFITS, FREE_TIER_SUMMARY, PRICING_PLANS } from '@/lib/pricing'

interface PlanColumn {
  key: string
  name: string
  price: string
  term: string
  meta?: string
  desc: string
  featured: boolean
}

const PLAN_DESC: Record<string, string> = {
  monthly: '全部功能不限量。',
  quarterly: '全部功能不限量。',
  yearly: '一年安心用到考前。',
}

/* 免费列 + PRICING_PLANS 三档 = 四列。 */
const COLUMNS: readonly PlanColumn[] = [
  { key: 'free', name: '免费', price: '¥0', term: '永久', desc: FREE_TIER_SUMMARY, featured: false },
  ...PRICING_PLANS.map((plan) => ({
    key: plan.id,
    name: plan.name,
    price: formatYuan(plan.amountCents),
    term: `/ ${plan.durationDays} 天`,
    meta: plan.perMonthNote,
    desc: PLAN_DESC[plan.id] ?? '全部功能不限量。',
    featured: plan.recommended === true,
  })),
]

/** 权益单元格:✓→yes、—→no、其余→val。 */
function benefitCell(v: string) {
  if (v === '✓') return <td className="yes">有</td>
  if (v === '—') return <td className="no">—</td>
  return <td className="val num">{v}</td>
}

/** #pricing 定价:四列方案(推荐列深色 featured)+ 权益对比表。数据来自 lib/pricing。 */
export function PricingSection() {
  const { data: user } = useAuth()
  const loggedIn = Boolean(user)

  const ctaFor = (key: string): { label: string; to: string } => {
    if (loggedIn) {
      return key === 'free'
        ? { label: '进入工作台 →', to: PATHS.dashboard }
        : { label: '去开通会员 →', to: PATHS.membership }
    }
    return key === 'free'
      ? { label: '免费开始', to: PATHS.login }
      : { label: '注册后开通', to: PATHS.login }
  }

  return (
    <section className="section" id="pricing">
      <div className="l-wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow-row"><span className="idx accent">PRICING</span><hr className="hairline" /></div>
            <h2 className="h-sec">定价</h2>
          </div>
          <p className="lead">免费额度每天刷新，会员按需开通——先用免费额度出一份卷子，再决定要不要付费。</p>
        </div>

        <div className="price-grid">
          {COLUMNS.map((col) => {
            const cta = ctaFor(col.key)
            return (
              <div className={`plan${col.featured ? ' featured' : ''}`} key={col.key}>
                {col.featured && <div className="badge">推荐</div>}
                <div className="pname">{col.name}</div>
                <div className="pprice num"><span className="cur">{col.price.slice(0, 1)}</span>{col.price.slice(1)}</div>
                <div className="pterm">{col.term}</div>
                <div className="pmeta num">{col.meta ?? ''}</div>
                <div className="pdesc">{col.desc}</div>
                <Link to={cta.to} className={`btn${col.featured ? ' btn--primary' : ''}`}>{cta.label}</Link>
              </div>
            )
          })}
        </div>

        <div className="rights">
          <table className="rights-tbl">
            <caption>权益对比 · Free vs. Member</caption>
            <thead>
              <tr><th>功能</th><th>免费</th><th>会员</th></tr>
            </thead>
            <tbody>
              {BENEFITS.map((b) => (
                <tr key={b.feature}>
                  <td>{b.feature}</td>
                  {benefitCell(b.free)}
                  {benefitCell(b.member)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="price-note">到期不自动续费；续费从当前有效期顺延。</p>
      </div>
    </section>
  )
}

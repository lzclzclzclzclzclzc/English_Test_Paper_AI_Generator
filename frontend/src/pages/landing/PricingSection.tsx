import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { formatYuan } from '@/lib/money'
import { PATHS } from '@/lib/paths'
import { FREE_TIER_SUMMARY, PRICE_ROWS, PRICING_PACKS } from '@/lib/pricing'

interface PlanColumn {
  key: string
  name: string
  price: string
  term: string
  meta?: string
  desc: string
  featured: boolean
}

const PACK_DESC: Record<string, string> = {
  starter: '约 20 张 AI 改编卷。',
  standard: '约 60 张 AI 改编卷。',
  annual: '一次充足，用到考前。',
}

/* 免费列 + PRICING_PACKS 三档 = 四列。 */
const COLUMNS: readonly PlanColumn[] = [
  { key: 'free', name: '免费', price: '¥0', term: '永久', desc: FREE_TIER_SUMMARY, featured: false },
  ...PRICING_PACKS.map((pack) => ({
    key: pack.id,
    name: pack.name,
    price: formatYuan(pack.amountCents),
    term: `/ ${pack.credits.toLocaleString()} 积分`,
    meta: pack.note,
    desc: PACK_DESC[pack.id] ?? '',
    featured: pack.recommended === true,
  })),
]

/** 价目单元格:免费→yes,其余→val。 */
function costCell(v: string) {
  if (v === '免费') return <td className="yes">免费</td>
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
        : { label: '去充值 →', to: PATHS.credits }
    }
    return key === 'free'
      ? { label: '免费开始', to: PATHS.login }
      : { label: '注册后充值', to: PATHS.login }
  }

  return (
    <section className="section" id="pricing">
      <div className="l-wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow-row"><span className="idx accent">PRICING</span><hr className="hairline" /></div>
            <h2 className="h-sec">定价</h2>
          </div>
          <p className="lead">按次扣积分，用多少付多少——注册和每天都送免费积分，先出几份卷子再决定要不要充值。</p>
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
            <caption>价目 · 积分怎么扣</caption>
            <thead>
              <tr><th>功能</th><th>积分</th></tr>
            </thead>
            <tbody>
              {PRICE_ROWS.map((r) => (
                <tr key={r.feature}>
                  <td>{r.feature}</td>
                  {costCell(r.cost)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="price-note">积分不过期、不订阅；出卷失败原路退回。每日赠送当日有效。</p>
      </div>
    </section>
  )
}

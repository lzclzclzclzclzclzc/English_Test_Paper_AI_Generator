import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { PATHS } from '@/lib/paths'
import { scrollToAnchor } from './shared'

const NAV = [
  { id: 'types', label: '功能' },
  { id: 'engine', label: '引擎' },
  { id: 'pricing', label: '定价' },
  { id: 'faq', label: '常见问题' },
] as const

/** 深色粘顶页眉:品牌 mark「卷」+ 品牌名 + 锚点导航 + useAuth 三态(加载占位/未登录双钮/已登录单钮)。 */
export function LandingHeader() {
  const { data: user, isLoading } = useAuth()

  return (
    <header className="site-header">
      <div className="l-wrap">
        <nav className="nav" aria-label="主导航">
          <a className="brand" href="#top">
            <span className="mark">卷</span>
            <span>卷王</span>
          </a>
          <div className="links">
            {NAV.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                onClick={(e) => scrollToAnchor(e, item.id)}
              >
                {item.label}
              </a>
            ))}
          </div>
          <div className="actions">
            {isLoading ? (
              <span aria-hidden style={{ width: 150, height: 34 }} />
            ) : user ? (
              <Link to={PATHS.dashboard} className="btn btn--primary">
                进入工作台 →
              </Link>
            ) : (
              <>
                <Link to={PATHS.login} className="login">
                  登录
                </Link>
                <Link to={PATHS.login} className="btn btn--primary">
                  免费开始
                </Link>
              </>
            )}
          </div>
        </nav>
      </div>
    </header>
  )
}

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

const PRIMARY_BTN =
  'rounded-sm border border-accent bg-wash px-4 py-1.5 font-ui text-[14px] text-ink transition-colors hover:text-accent'

/** 粘顶毛玻璃页眉:品牌字 + 锚点导航 + useAuth 三态(加载占位 / 未登录双钮 / 已登录单钮)。 */
export function LandingHeader() {
  const { data: user, isLoading } = useAuth()

  return (
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
          {NAV.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              onClick={(e) => scrollToAnchor(e, item.id)}
              className="text-[14px] text-muted-ink transition-colors hover:text-accent max-sm:hidden"
            >
              {item.label}
            </a>
          ))}
          {isLoading ? (
            /* 定宽占位:避免 auth 落定时右侧按钮跳动 */
            <span aria-hidden className="h-[34px] w-[150px]" />
          ) : user ? (
            <Link to={PATHS.home} className={PRIMARY_BTN}>
              进入工作台 →
            </Link>
          ) : (
            <>
              <Link
                to={PATHS.login}
                className="text-[14px] text-muted-ink transition-colors hover:text-accent"
              >
                登录
              </Link>
              <Link to={PATHS.login} className={PRIMARY_BTN}>
                免费开始
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}

import { Link } from 'react-router-dom'
import { PATHS } from '@/lib/paths'
import { FREE_GENERATE_PER_DAY } from '@/lib/quota'

/** 深色 final CTA 带 + 深色页脚（品牌名「卷王」）。 */
export function FooterCta() {
  return (
    <>
      <section className="final" aria-label="立即开始">
        <div className="l-wrap">
          <div className="final-grid">
            <div>
              <h2>出一份卷子，看看 AI 有多懂中考英语。</h2>
              <p className="fsub">
                免费注册<span className="dot">·</span>每天 {FREE_GENERATE_PER_DAY} 次出卷额度
              </p>
            </div>
            <div className="cta-side">
              <Link to={PATHS.login} className="btn btn--primary btn--lg">免费出一份卷子 →</Link>
            </div>
          </div>
        </div>
      </section>

      <footer className="site-footer">
        <div className="l-wrap">
          <div className="foot">
            <span className="brand-f">卷王</span>
            <span className="sep">·</span>
            <span>© 2026</span>
            <span className="sep">｜</span>
            <span className="links-f">
              <a href="#">关于我们</a>
              <a href="#">联系我们</a>
              <a href="#">用户协议</a>
              <a href="#">隐私政策</a>
            </span>
            <span className="icp">沪ICP备XXXXXXXX号</span>
          </div>
        </div>
      </footer>
    </>
  )
}

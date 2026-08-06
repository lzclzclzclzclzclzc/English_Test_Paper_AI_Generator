import { Link } from 'react-router-dom'
import { PATHS } from '@/lib/paths'
import { FREE_GENERATE_PER_DAY } from '@/lib/quota'

/** 尾部 CTA 条(左句右钮)+ 页脚(品牌 © / 占位链接 / 备案号占位)。 */
export function FooterCta() {
  return (
    <>
      <section className="flex flex-wrap items-center justify-between gap-6 border-t border-hairline py-16">
        <div>
          <p className="text-[24px] text-ink [font-family:var(--font-display)]">
            出一份卷子，看看 AI 有多懂中考英语。
          </p>
          <p className="mt-2 text-[13px] text-quiet">
            免费注册 · 每天 {FREE_GENERATE_PER_DAY} 次出卷额度
          </p>
        </div>
        <Link
          to={PATHS.login}
          className="rounded-sm border border-accent bg-wash px-7 py-3 font-ui text-[15px] tracking-[0.05em] text-ink transition-colors hover:text-accent"
        >
          免费出一份卷子 →
        </Link>
      </section>
      <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-hairline py-10 text-[13px] text-quiet">
        <span>中考英语 AI 试卷生成器 · © 2026</span>
        {/* 占位:上线前替换为真实页面链接 */}
        <span>关于我们 · 联系我们 · 用户协议 · 隐私政策</span>
        <span>沪ICP备XXXXXXXX号</span>
      </footer>
    </>
  )
}

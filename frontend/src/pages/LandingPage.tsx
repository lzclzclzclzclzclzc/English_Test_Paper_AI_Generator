import { LandingHeader } from './landing/LandingHeader'
import { HeroSection } from './landing/HeroSection'
import { StatsBar } from './landing/StatsBar'
import { TypeGrid } from './landing/TypeGrid'
import { EngineSection } from './landing/EngineSection'
import { LoopSection } from './landing/LoopSection'
import { AssistantSection } from './landing/AssistantSection'
import { ParentsSection } from './landing/ParentsSection'
import { PricingSection } from './landing/PricingSection'
import { FaqSection } from './landing/FaqSection'
import { FooterCta } from './landing/FooterCta'

/**
 * 营销首页(`/`,对所有人可见;已登录时页眉 CTA 变「进入工作台」)。纯静态:除 useAuth 外零请求。
 * 卷王品牌视觉(variant-5 SaaS × Swiss):外层 .landing-swiss 承载作用域样式与深/浅区块色板;
 * 每个 section 自带 .l-wrap 控制最大宽度(深色区块 Hero/Footer 需要全宽铺底)。
 * 11 段结构拆在 pages/landing/ 子组件里,本文件只做组装。
 */
export function LandingPage() {
  return (
    <div className="landing-swiss min-h-svh">
      <LandingHeader />
      <main id="top">
        <HeroSection />
        <StatsBar />
        <TypeGrid />
        <EngineSection />
        <LoopSection />
        <AssistantSection />
        <ParentsSection />
        <PricingSection />
        <FaqSection />
        <FooterCta />
      </main>
    </div>
  )
}

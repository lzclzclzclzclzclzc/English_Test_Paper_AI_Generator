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
 * 11 段结构拆在 pages/landing/ 子组件里,本文件只做组装。
 */
export function LandingPage() {
  return (
    <div className="min-h-svh bg-background">
      <LandingHeader />
      <main className="mx-auto max-w-[1180px] px-14 max-md:px-6">
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

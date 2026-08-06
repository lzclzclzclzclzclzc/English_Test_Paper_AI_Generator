/**
 * 全站路径常量(路由重构后唯一事实来源)。
 * `/` 是双态入口:未登录 = 营销首页,已登录 = 工作台(见 HomeGate)。
 */
export const PATHS = {
  home: '/',
  /** legacy 营销页地址,路由层重定向到 home */
  welcome: '/welcome',
  login: '/login',
  /** 一句话出卷(原生成页,自 `/` 迁出) */
  generate: '/generate',
  practice: '/practice',
  practiceType: (slug: string) => `/practice/${slug}`,
  practiceCustom: '/practice/custom',
  mock: '/mock',
  papers: '/papers',
  paper: (id: string) => `/papers/${id}`,
  review: '/review',
  mastery: '/mastery',
  studyPlan: '/study-plan',
  membership: '/membership',
  settings: '/settings',
  assistant: '/assistant',
  admin: '/admin',
} as const

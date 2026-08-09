/**
 * 全站路径常量(路由重构后唯一事实来源)。
 * `/` 对所有人都是营销首页;登录后的工作台在 `/home`(首页页眉「进入工作台」可达)。
 */
export const PATHS = {
  home: '/',
  /** 登录后工作台 */
  dashboard: '/home',
  /** legacy 营销页地址,路由层重定向到 home */
  welcome: '/welcome',
  login: '/login',
  /** 一句话出卷(原生成页,自 `/` 迁出) */
  generate: '/generate',
  /** 每日一练(今日配方 + 一周安排) */
  daily: '/daily',
  /** 主题出卷(话题 × 语法题型) */
  themes: '/themes',
  /** 学情报告(会员,打印友好,自掌握度页独立) */
  report: '/report',
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

import type { WrongItemRef } from '@/types/api'

/**
 * 成绩视图「错题巩固」→ 生成页的一次性导航握手（D2）。
 * 经 react-router navigate state 传递，生成页读取一次后立即清除；
 * 刷新即失效（Spec D § 3.4 的产品决策）。
 */
export interface RemediationHandoff {
  wrongItems: WrongItemRef[]
  sourcePaperTitle: string
}

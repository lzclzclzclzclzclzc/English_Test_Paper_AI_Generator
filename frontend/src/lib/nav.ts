import {
  BadgeCheck,
  BarChart3,
  CalendarCheck,
  Home,
  LayoutDashboard,
  LayoutGrid,
  List,
  MessageCircle,
  ScrollText,
  Timer,
  Users,
  XCircle,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { PATHS } from '@/lib/paths'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end: boolean
  /** 未上线入口:渲染为不可点的占位项 */
  disabled?: boolean
  /** 角标文案(如「即将上线」) */
  badge?: string
}

export interface NavGroup {
  label: string
  items: readonly NavItem[]
}

/** 普通用户侧栏:三组九项;设置不在组内,固定在底部用户区。 */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    label: '练习',
    items: [
      { to: PATHS.home, label: '工作台', icon: Home, end: true },
      { to: PATHS.practice, label: '练习中心', icon: LayoutGrid, end: true },
      { to: PATHS.mock, label: '整卷模拟', icon: Timer, end: true },
      { to: PATHS.assistant, label: '学习助手', icon: MessageCircle, end: true },
    ],
  },
  {
    label: '复盘',
    items: [
      { to: PATHS.review, label: '错题本', icon: XCircle, end: true },
      { to: PATHS.mastery, label: '掌握度', icon: BarChart3, end: true },
      { to: PATHS.studyPlan, label: '学习计划', icon: CalendarCheck, end: true },
    ],
  },
  {
    label: '我的',
    items: [
      { to: PATHS.papers, label: '历史试卷', icon: List, end: false },
      { to: PATHS.membership, label: '会员', icon: BadgeCheck, end: true },
    ],
  },
]

export const ADMIN_GROUPS: readonly NavGroup[] = [
  {
    label: '管理后台',
    items: [
      { to: PATHS.admin, label: '概览', icon: LayoutDashboard, end: true },
      { to: '/admin/analytics', label: '分析', icon: BarChart3, end: true },
      { to: '/admin/users', label: '用户', icon: Users, end: false },
      { to: '/admin/memberships', label: '会员', icon: BadgeCheck, end: true },
      { to: '/admin/orders', label: '订单', icon: ScrollText, end: true },
    ],
  },
]

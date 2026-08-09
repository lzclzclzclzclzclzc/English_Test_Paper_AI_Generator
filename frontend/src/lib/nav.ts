import {
  BadgeCheck,
  BarChart3,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  FileText,
  Home,
  LayoutDashboard,
  LayoutGrid,
  MessageCircle,
  PenLine,
  ScrollText,
  SlidersHorizontal,
  Tags,
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

/**
 * 普通用户侧栏:四组十三项。
 * 历史试卷/会员/设置不在组内——收进底部头像个人菜单(Sidebar.tsx)。
 */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    label: '练习',
    items: [
      { to: PATHS.dashboard, label: '工作台', icon: Home, end: true },
      { to: PATHS.daily, label: '每日一练', icon: CalendarDays, end: true },
      { to: PATHS.practice, label: '练习中心', icon: LayoutGrid, end: true },
      {
        to: '/vocabulary',
        label: '词汇学习',
        icon: BookOpen,
        end: true,
        disabled: true,
        badge: '即将上线',
      },
    ],
  },
  {
    label: '出卷',
    items: [
      { to: PATHS.themes, label: '主题出卷', icon: Tags, end: true },
      { to: PATHS.practiceCustom, label: '自选组卷', icon: SlidersHorizontal, end: true },
      { to: PATHS.mock, label: '整卷模拟', icon: Timer, end: true },
      { to: PATHS.generate, label: '一句话出卷', icon: PenLine, end: true },
    ],
  },
  {
    label: '助手',
    items: [
      { to: PATHS.assistant, label: '学习助手', icon: MessageCircle, end: true },
      { to: PATHS.studyPlan, label: '学习计划', icon: CalendarCheck, end: true },
    ],
  },
  {
    label: '复盘',
    items: [
      { to: PATHS.review, label: '错题本', icon: XCircle, end: true },
      { to: PATHS.mastery, label: '掌握度', icon: BarChart3, end: true },
      { to: PATHS.report, label: '学情报告', icon: FileText, end: true },
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

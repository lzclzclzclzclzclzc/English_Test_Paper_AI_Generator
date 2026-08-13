import {
  BadgeCheck,
  BarChart3,
  BookOpen,
  BookOpenCheck,
  CalendarCheck,
  CalendarDays,
  FileText,
  Home,
  LayoutDashboard,
  LayoutGrid,
  MessageCircle,
  Network,
  PenLine,
  ScrollText,
  SlidersHorizontal,
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
  /** 空字符串 = 无分组标题，直接作为顶级项渲染（如 主页 / 学习助手） */
  label: string
  items: readonly NavItem[]
}

/**
 * 普通用户侧栏：两个顶级项（主页 / 学习助手）+ 四个分组（练习 / 出卷 / 背词 / 复盘）。
 * 会员/设置不在组内——收进底部头像个人菜单(Sidebar.tsx)。
 */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    label: '',
    items: [
      { to: PATHS.dashboard, label: '主页', icon: Home, end: true },
      { to: PATHS.assistant, label: '学习助手', icon: MessageCircle, end: true },
    ],
  },
  {
    label: '练习',
    items: [
      { to: PATHS.studyPlan, label: '学习计划', icon: CalendarCheck, end: true },
      { to: PATHS.daily, label: '每日一练', icon: CalendarDays, end: true },
      { to: PATHS.practice, label: '练习中心', icon: LayoutGrid, end: true },
    ],
  },
  {
    label: '出卷',
    items: [
      { to: PATHS.generate, label: '一句话出卷', icon: PenLine, end: true },
      { to: PATHS.practiceCustom, label: '自选组卷', icon: SlidersHorizontal, end: true },
      { to: PATHS.mock, label: '整卷模拟', icon: Timer, end: true },
    ],
  },
  {
    label: '背词',
    items: [
      { to: PATHS.vocabulary, label: '背单词', icon: BookOpen, end: true },
      { to: PATHS.vocabularyProgress, label: '背词进度', icon: BookOpenCheck, end: true },
    ],
  },
  {
    label: '复盘',
    items: [
      { to: PATHS.papers, label: '历史试卷', icon: ScrollText, end: true },
      { to: PATHS.mindmaps, label: '思维导图', icon: Network, end: true },
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

import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/components/RequireAuth'
import { AppLayout } from '@/components/AppLayout'
import { LandingPage } from '@/pages/LandingPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { LoginPage } from '@/pages/LoginPage'
import { GeneratePage } from '@/pages/GeneratePage'
import { DailyPage } from '@/pages/DailyPage'
import { ThemesPage } from '@/pages/ThemesPage'
import { ReportPage } from '@/pages/ReportPage'
import { PracticePage } from '@/pages/PracticePage'
import { DrillPage } from '@/pages/DrillPage'
import { CustomPaperPage } from '@/pages/CustomPaperPage'
import { MockPage } from '@/pages/MockPage'
import { AssistantPage } from '@/pages/AssistantPage'
import { PapersPage } from '@/pages/PapersPage'
import { PaperPageRoute } from '@/pages/PaperPage'
import { MasteryPage } from '@/pages/MasteryPage'
import { MembershipPage } from '@/pages/MembershipPage'
import { ReviewPage } from '@/pages/ReviewPage'
import { StudyPlanPage } from '@/pages/StudyPlanPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { RequireAdmin } from '@/components/RequireAdmin'
import { RedirectIfAdmin } from '@/components/RedirectIfAdmin'
import { AdminLayout } from '@/pages/admin/AdminLayout'
import { AdminOverviewPage } from '@/pages/admin/AdminOverviewPage'
import { AdminAnalyticsPage } from '@/pages/admin/AdminAnalyticsPage'
import { AdminUsersPage } from '@/pages/admin/AdminUsersPage'
import { AdminUserDetailPage } from '@/pages/admin/AdminUserDetailPage'
import { AdminMembershipsPage } from '@/pages/admin/AdminMembershipsPage'
import { AdminOrdersPage } from '@/pages/admin/AdminOrdersPage'
import { VocabularyPage } from '@/pages/VocabularyPage'
import { VocabularyProgressPage } from '@/pages/VocabularyProgressPage'
import { PATHS } from '@/lib/paths'

export function AppRoutes() {
  return (
    <Routes>
      {/* `/` 对所有人都是营销首页(已登录时页眉 CTA 变「进入工作台」→ /home) */}
      <Route path={PATHS.home} element={<LandingPage />} />
      <Route path={PATHS.welcome} element={<Navigate to={PATHS.home} replace />} />
      <Route path={PATHS.login} element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path={PATHS.dashboard} element={<RedirectIfAdmin><DashboardPage /></RedirectIfAdmin>} />
        <Route path={PATHS.generate} element={<RedirectIfAdmin><GeneratePage /></RedirectIfAdmin>} />
        <Route path={PATHS.daily} element={<RedirectIfAdmin><DailyPage /></RedirectIfAdmin>} />
        <Route path={PATHS.themes} element={<RedirectIfAdmin><ThemesPage /></RedirectIfAdmin>} />
        <Route path={PATHS.report} element={<RedirectIfAdmin><ReportPage /></RedirectIfAdmin>} />
        <Route path={PATHS.practice} element={<RedirectIfAdmin><PracticePage /></RedirectIfAdmin>} />
        <Route path={PATHS.practiceCustom} element={<RedirectIfAdmin><CustomPaperPage /></RedirectIfAdmin>} />
        <Route path="/practice/:slug" element={<RedirectIfAdmin><DrillPage /></RedirectIfAdmin>} />
        <Route path={PATHS.mock} element={<RedirectIfAdmin><MockPage /></RedirectIfAdmin>} />
        <Route path={PATHS.assistant} element={<RedirectIfAdmin><AssistantPage /></RedirectIfAdmin>} />
        <Route path={PATHS.review} element={<RedirectIfAdmin><ReviewPage /></RedirectIfAdmin>} />
        <Route path={PATHS.papers} element={<RedirectIfAdmin><PapersPage /></RedirectIfAdmin>} />
        <Route
          path="/papers/:paperId"
          element={<RedirectIfAdmin><PaperPageRoute /></RedirectIfAdmin>}
        />
        <Route path={PATHS.mastery} element={<RedirectIfAdmin><MasteryPage /></RedirectIfAdmin>} />
        <Route path={PATHS.studyPlan} element={<RedirectIfAdmin><StudyPlanPage /></RedirectIfAdmin>} />
        <Route path={PATHS.vocabulary} element={<RedirectIfAdmin><VocabularyPage /></RedirectIfAdmin>} />
        <Route path={PATHS.vocabularyProgress} element={<RedirectIfAdmin><VocabularyProgressPage /></RedirectIfAdmin>} />
        <Route path={PATHS.membership} element={<RedirectIfAdmin><MembershipPage /></RedirectIfAdmin>} />
        <Route path={PATHS.settings} element={<RedirectIfAdmin><SettingsPage /></RedirectIfAdmin>} />
        <Route
          path={PATHS.admin}
          element={
            <RequireAdmin>
              <AdminLayout />
            </RequireAdmin>
          }
        >
          <Route index element={<AdminOverviewPage />} />
          <Route path="analytics" element={<AdminAnalyticsPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="users/:userId" element={<AdminUserDetailPage />} />
          <Route path="memberships" element={<AdminMembershipsPage />} />
          <Route path="orders" element={<AdminOrdersPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to={PATHS.home} replace />} />
    </Routes>
  )
}

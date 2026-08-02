import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/components/RequireAuth'
import { AppLayout } from '@/components/AppLayout'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/LoginPage'
import { GeneratePage } from '@/pages/GeneratePage'
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
import { AdminUsersPage } from '@/pages/admin/AdminUsersPage'
import { AdminUserDetailPage } from '@/pages/admin/AdminUserDetailPage'
import { AdminMembershipsPage } from '@/pages/admin/AdminMembershipsPage'
import { AdminOrdersPage } from '@/pages/admin/AdminOrdersPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/welcome" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<RedirectIfAdmin><GeneratePage /></RedirectIfAdmin>} />
        <Route path="/assistant" element={<RedirectIfAdmin><AssistantPage /></RedirectIfAdmin>} />
        <Route path="/review" element={<RedirectIfAdmin><ReviewPage /></RedirectIfAdmin>} />
        <Route path="/papers" element={<RedirectIfAdmin><PapersPage /></RedirectIfAdmin>} />
        <Route
          path="/papers/:paperId"
          element={<RedirectIfAdmin><PaperPageRoute /></RedirectIfAdmin>}
        />
        <Route path="/mastery" element={<RedirectIfAdmin><MasteryPage /></RedirectIfAdmin>} />
        <Route path="/study-plan" element={<RedirectIfAdmin><StudyPlanPage /></RedirectIfAdmin>} />
        <Route path="/membership" element={<RedirectIfAdmin><MembershipPage /></RedirectIfAdmin>} />
        <Route path="/settings" element={<RedirectIfAdmin><SettingsPage /></RedirectIfAdmin>} />
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminLayout />
            </RequireAdmin>
          }
        >
          <Route index element={<AdminOverviewPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="users/:userId" element={<AdminUserDetailPage />} />
          <Route path="memberships" element={<AdminMembershipsPage />} />
          <Route path="orders" element={<AdminOrdersPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

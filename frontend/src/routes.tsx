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
        <Route path="/" element={<GeneratePage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/papers" element={<PapersPage />} />
        <Route path="/papers/:paperId" element={<PaperPageRoute />} />
        <Route path="/mastery" element={<MasteryPage />} />
        <Route path="/study-plan" element={<StudyPlanPage />} />
        <Route path="/membership" element={<MembershipPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/components/RequireAuth'
import { AppLayout } from '@/components/AppLayout'
import { LoginPage } from '@/pages/LoginPage'
import { GeneratePage } from '@/pages/GeneratePage'
import { PapersPage } from '@/pages/PapersPage'
import { PaperPageRoute } from '@/pages/PaperPage'
import { MasteryPage } from '@/pages/MasteryPage'
import { MembershipPage } from '@/pages/MembershipPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<GeneratePage />} />
        <Route path="/papers" element={<PapersPage />} />
        <Route path="/papers/:paperId" element={<PaperPageRoute />} />
        <Route path="/mastery" element={<MasteryPage />} />
        <Route path="/membership" element={<MembershipPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

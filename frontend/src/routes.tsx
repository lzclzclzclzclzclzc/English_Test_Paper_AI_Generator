import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/components/RequireAuth'
import { AppLayout } from '@/components/AppLayout'
import { LoginPage } from '@/pages/LoginPage'
import { GeneratePage } from '@/pages/GeneratePage'
import { PaperPageRoute } from '@/pages/PaperPage'
import { MasteryPage } from '@/pages/MasteryPage'

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
        {/* 为将来的试卷列表页占位；现在重定向回生成页 */}
        <Route path="/papers" element={<Navigate to="/" replace />} />
        <Route path="/papers/:paperId" element={<PaperPageRoute />} />
        <Route path="/mastery" element={<MasteryPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

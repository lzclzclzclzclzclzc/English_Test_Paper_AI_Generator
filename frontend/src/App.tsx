import { useEffect } from 'react'
import { BrowserRouter, useNavigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/queryClient'
import { AppRoutes } from '@/routes'
import { Toaster } from '@/components/ui/sonner'

/** 把 React Router 的 navigate 暴露给 queryClient 的全局 401 处理（Spec D § 6.4）。 */
function NavigateBridge() {
  const navigate = useNavigate()
  useEffect(() => {
    window.__appNavigate = navigate
    return () => {
      delete window.__appNavigate
    }
  }, [navigate])
  return null
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <NavigateBridge />
        <AppRoutes />
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App

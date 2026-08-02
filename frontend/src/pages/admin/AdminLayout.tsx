import { Outlet } from 'react-router-dom'

export function AdminLayout() {
  return (
    <div className="mx-auto w-full max-w-[1040px] p-8">
      <Outlet />
    </div>
  )
}

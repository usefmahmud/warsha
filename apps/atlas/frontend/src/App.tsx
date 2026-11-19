import { Navigate, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { Spinner } from './components/ui'
import { useAuth } from './auth'
import { BoardScreen } from './screens/Board'
import { ListScreen } from './screens/TicketList'
import { LoginScreen } from './screens/Login'
import { MyWorkScreen } from './screens/MyWork'
import { ProjectsScreen } from './screens/Projects'
import { TicketScreen } from './screens/TicketDetail'

function Protected({ children }: { children: React.ReactNode }) {
  const { user, booting } = useAuth()
  if (booting) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Spinner label="بيتحقق من الجلسة…" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Shell>{children}</Shell>
}

export function App() {
  const { user, booting } = useAuth()
  return (
    <Routes>
      <Route
        path="/login"
        element={booting ? <div className="grid min-h-dvh place-items-center"><Spinner /></div> : user ? <Navigate to="/projects" replace /> : <LoginScreen />}
      />
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<Protected><ProjectsScreen /></Protected>} />
      <Route path="/my" element={<Protected><MyWorkScreen /></Protected>} />
      <Route path="/p/:projectKey" element={<Navigate to="board" replace />} />
      <Route path="/p/:projectKey/board" element={<Protected><BoardScreen /></Protected>} />
      <Route path="/p/:projectKey/list" element={<Protected><ListScreen /></Protected>} />
      <Route path="/p/:projectKey/t/:ticketKey" element={<Protected><TicketScreen /></Protected>} />
      <Route path="/t/:ticketKey" element={<Protected><TicketScreen /></Protected>} />
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  )
}

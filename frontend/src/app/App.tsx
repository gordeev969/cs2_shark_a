import { lazy, Suspense } from 'react'
import { Route, Routes, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/entities/auth'
import { AuthProvider } from './providers/AuthProvider'
import { AppShell } from '@/widgets/app-shell'
import { SettingsProvider } from './providers/SettingsProvider'

const DashboardPage = lazy(() =>
  import('@/pages/dashboard').then((m) => ({ default: m.DashboardPage })),
)
const ImportPage = lazy(() =>
  import('@/pages/import-demo').then((m) => ({ default: m.ImportPage })),
)
const MatchesPage = lazy(() => import('@/pages/matches').then((m) => ({ default: m.MatchesPage })))
const MatchPage = lazy(() =>
  import('@/pages/match-details').then((m) => ({ default: m.MatchPage })),
)
const PlayersPage = lazy(() => import('@/pages/players').then((m) => ({ default: m.PlayersPage })))
const PlayerPage = lazy(() =>
  import('@/pages/player-profile').then((m) => ({ default: m.PlayerPage })),
)
const SettingsPage = lazy(() =>
  import('@/pages/settings').then((m) => ({ default: m.SettingsPage })),
)
const NotFoundPage = lazy(() =>
  import('@/pages/not-found').then((m) => ({ default: m.NotFoundPage })),
)

const LoginPage = lazy(() => import('@/pages/login').then((m) => ({ default: m.LoginPage })))
const ConnectPage = lazy(() =>
  import('@/pages/connect-cs2').then((m) => ({ default: m.ConnectPage })),
)
function ProtectedLayout() {
  const { authenticated, required } = useAuth()
  if (required && !authenticated) return <Navigate to="/login" replace />
  return (
    <SettingsProvider>
      <AppShell>
        <Outlet />
      </AppShell>
    </SettingsProvider>
  )
}
function LoginRoute() {
  const { authenticated } = useAuth()
  return authenticated ? <Navigate to="/" replace /> : <LoginPage />
}
export default function App() {
  return (
    <AuthProvider>
      <Suspense
        fallback={
          <div className="loading" role="status">
            Открываем страницу…
          </div>
        }
      >
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/import" element={<ImportPage />} />
            <Route path="/matches" element={<MatchesPage />} />
            <Route path="/matches/:id" element={<MatchPage />} />
            <Route path="/players" element={<PlayersPage />} />
            <Route path="/players/:steamId" element={<PlayerPage />} />
            <Route path="/connect" element={<ConnectPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </Suspense>
    </AuthProvider>
  )
}

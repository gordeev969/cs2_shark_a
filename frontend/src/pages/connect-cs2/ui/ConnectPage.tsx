import { isSnapshotMode } from '@/shared/config'
import { Link } from 'react-router-dom'
import { useAuth } from '@/entities/auth'
import { CS2ConnectionForm } from '@/features/connect-cs2'
import { SteamSignIn } from '@/features/steam-session'
import { Title, ReadonlyNotice } from '@/shared/ui'
export function ConnectPage() {
  const { authenticated } = useAuth()
  return (
    <>
      <Title
        eyebrow="ПРОФИЛЬ / ПОДКЛЮЧЕНИЕ"
        title="Подключите историю CS2"
        subtitle="Один раз дайте доступ к матчам — затем обновляйте историю в своём дашборде."
      />
      {isSnapshotMode ? (
        <ReadonlyNotice />
      ) : authenticated ? (
        <CS2ConnectionForm />
      ) : (
        <section className="panel">
          <h2>Сначала войдите через Steam</h2>
          <p className="muted">Для подключения истории нужно подтвердить свой аккаунт.</p>
          <SteamSignIn />
          <p>
            <Link to="/import" className="text-link">
              Или импортировать демку локально
            </Link>
          </p>
        </section>
      )}
    </>
  )
}

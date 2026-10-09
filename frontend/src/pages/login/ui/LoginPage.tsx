import { isSnapshotMode } from '@/shared/config'
import { Link, useSearchParams } from 'react-router-dom'
import { Crosshair, ShieldCheck, Swords, TrendingUp } from 'lucide-react'
import { SteamSignIn } from '@/features/steam-session'
import { useAuth } from '@/entities/auth'
export function LoginPage() {
  const { required } = useAuth()
  const [params] = useSearchParams()
  return (
    <div className="auth-stage">
      <section className="auth-card panel">
        <div className="brand auth-brand">
          <div className="brand-mark">
            <Crosshair size={28} />
          </div>
          <strong>
            PREMIER<span>ANALYZER</span>
          </strong>
        </div>
        <span className="tag">ВАША ИГРА ПОД МИКРОСКОПОМ</span>
        <h1>
          Ваш профиль.
          <br />
          Каждый матч.
          <br />
          <span>Больше понимания.</span>
        </h1>
        <p className="muted">
          Войдите через Steam, подключите историю CS2 и разбирайте свою игру по настоящим демкам.
        </p>
        {params.has('error') && (
          <p className="error-box" role="alert">
            Steam не подтвердил вход. Повторите авторизацию.
          </p>
        )}
        <SteamSignIn />
        <p className="muted tiny">
          Пароль вводится только на сайте Steam. Приложение получает ваш SteamID.
        </p>
        <div className="auth-benefits">
          <span>
            <Swords size={18} /> Последние матчи
          </span>
          <span>
            <TrendingUp size={18} /> Личная статистика
          </span>
          <span>
            <ShieldCheck size={18} /> Локальная база
          </span>
        </div>
        {!required && (
          <Link className="text-link" to="/">
            {isSnapshotMode ? 'Открыть опубликованный дашборд' : 'Продолжить с локальными демками'}
          </Link>
        )}
      </section>
      <div className="auth-grid" aria-hidden="true" />
    </div>
  )
}

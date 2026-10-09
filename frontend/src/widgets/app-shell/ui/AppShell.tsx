import { isSnapshotMode } from '@/shared/config'
import { useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useData } from '@/shared/api'
import type { Health } from '@/shared/api/contracts'
import {
  LayoutDashboard,
  FileUp,
  Swords,
  Users,
  Settings2,
  Crosshair,
  Target,
  ShieldCheck,
  LockKeyhole,
  X,
  Menu,
} from 'lucide-react'
import { useAuth } from '@/entities/auth'
import { SteamSignOut } from '@/features/steam-session'
import { useSettings } from '@/entities/settings'

const navigation = [
  { to: '/', label: 'Обзор', icon: LayoutDashboard },
  { to: '/import', label: 'Импорт демки', icon: FileUp },
  { to: '/matches', label: 'Матчи', icon: Swords },
  { to: '/players', label: 'Игроки', icon: Users },
  { to: '/connect', label: 'Подключение CS2', icon: ShieldCheck },
  { to: '/settings', label: 'Настройки', icon: Settings2 },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { settings } = useSettings()
  const health = useData<Health>('/api/health')
  const [open, setOpen] = useState(false)
  return (
    <div className={`app ${settings?.compact ? 'compact' : ''}`}>
      <div className="mobile-bar">
        <Link to="/" className="brand">
          <Crosshair size={24} />
          <strong>
            PREMIER<span>ANALYZER</span>
          </strong>
        </Link>
        <button aria-label={open ? 'Закрыть меню' : 'Открыть меню'} onClick={() => setOpen(!open)}>
          {open ? <X /> : <Menu />}
        </button>
      </div>
      {open && (
        <button
          className="nav-scrim"
          aria-label="Закрыть навигацию"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <Link to="/" className="brand" onClick={() => setOpen(false)}>
          <div className="brand-mark">
            <Crosshair size={26} />
          </div>
          <strong>
            PREMIER<span>ANALYZER</span>
          </strong>
        </Link>
        <div className="sidebar-caption">ВАША ИГРА ПОД МИКРОСКОПОМ</div>
        <nav aria-label="Основная навигация">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setOpen(false)}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
              {item.to === '/import' && <span className="nav-plus">+</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-card">
            <span className="live-dot" />
            <strong>{isSnapshotMode ? 'Публичный отчёт' : 'Локальное пространство'}</strong>
            <p>{isSnapshotMode ? 'Настоящая контрольная демка.' : 'Ваш компьютер. Ваши данные.'}</p>
          </div>
          <Link to={user ? `/players/${user.steam_id64}` : '/settings'} className="sidebar-profile">
            <span className="avatar small">
              <Target size={17} />
            </span>
            <div>
              <strong>
                {user?.display_name ??
                  (isSnapshotMode
                    ? 'Выбранный игрок'
                    : settings?.steam_id64
                      ? 'Личный профиль настроен'
                      : 'Настройте свой профиль')}
              </strong>
              <span>{settings?.steam_id64 ? settings.steam_id64 : 'Выберите SteamID64'}</span>
            </div>
            <Settings2 size={15} />
          </Link>
          {user && <SteamSignOut />}
          <span className="sidebar-version">
            MVP 0.1 <span>CS2 / PREMIER</span>
          </span>
        </div>
      </aside>
      <div className="workspace">
        <div className="topbar">
          <span>
            <LockKeyhole size={13} />{' '}
            {isSnapshotMode ? 'Публичная контрольная демка' : 'Приватная библиотека'}
          </span>
          <span className={`api-status ${health.error ? 'offline' : ''}`}>
            <span className="live-dot" />
            {isSnapshotMode
              ? 'Режим просмотра'
              : health.loading
                ? 'Проверка API…'
                : health.error
                  ? 'API недоступен'
                  : 'Локальный API подключён'}
          </span>
        </div>
        <main>
          {isSnapshotMode && (
            <p className="notice">
              Режим просмотра · реальная демка Mirage из{' '}
              <a
                className="text-link"
                href="https://github.com/LaihoE/demoparser/blob/main/src/parser/test_demo.dem"
                target="_blank"
                rel="noreferrer"
              >
                demoparser2
              </a>
              . Для входа через Steam и своих матчей нужна серверная версия.
            </p>
          )}
          {children}
        </main>
        <footer>
          <span>CS2 Premier Analyzer</span>
          <span>
            <ShieldCheck size={12} />{' '}
            {isSnapshotMode
              ? 'Факты из демо. Серверный расчёт метрик.'
              : 'Факты из демо. Наблюдения по вашей истории.'}
          </span>
        </footer>
      </div>
    </div>
  )
}

import { isSnapshotMode, sourceRepository } from '@/shared/config'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
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
  X,
  Menu,
  ChevronRight,
  Search,
  Info,
  ArrowUpRight,
} from 'lucide-react'
import { useAuth } from '@/entities/auth'
import { SteamSignOut } from '@/features/steam-session'
import { useSettings } from '@/entities/settings'

const navigation = [
  { to: '/', label: 'Обзор', icon: LayoutDashboard },
  { to: '/matches', label: 'Матчи', icon: Swords },
  { to: '/players', label: 'Игроки', icon: Users },
  { to: '/import', label: 'Импорт демки', icon: FileUp },
  { to: '/connect', label: 'Подключение CS2', icon: ShieldCheck },
  { to: '/settings', label: 'Настройки', icon: Settings2 },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { settings } = useSettings()
  const health = useData<Health>('/api/health')
  const [open, setOpen] = useState(false)
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 700px)').matches)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 700px)')
    const change = (event: MediaQueryListEvent) => setMobile(event.matches)
    query.addEventListener('change', change)
    return () => query.removeEventListener('change', change)
  }, [])
  const { pathname } = useLocation()
  const section =
    navigation.find((item) => item.to !== '/' && pathname.startsWith(item.to))?.label ?? 'Обзор'
  useEffect(() => {
    if (!open) return
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', close)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener('keydown', close)
    }
  }, [open])
  return (
    <div className={`app ${settings?.compact ? 'compact' : ''}`}>
      <div className="mobile-bar">
        <Link to="/" className="brand">
          <Crosshair size={24} />
          <strong>
            PREMIER<span>ANALYZER</span>
          </strong>
        </Link>
        <button
          aria-label={open ? 'Закрыть меню' : 'Открыть меню'}
          aria-expanded={open}
          aria-controls="main-sidebar"
          onClick={() => setOpen(!open)}
        >
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
      <aside id="main-sidebar" className={`sidebar ${open ? 'open' : ''}`} inert={mobile && !open}>
        <Link to="/" className="brand" onClick={() => setOpen(false)}>
          <div className="brand-mark">
            <Crosshair size={26} />
          </div>
          <strong>
            PREMIER<span>ANALYZER</span>
          </strong>
        </Link>
        <div className="sidebar-caption">АНАЛИТИКА COUNTER-STRIKE 2</div>
        <nav aria-label="Основная навигация">
          {navigation.map((item, index) => (
            <div key={item.to} className="nav-item">
              {index === 0 && <div className="nav-group-title">АНАЛИТИКА</div>}
              {index === 3 && <div className="nav-group-title workspace-group">ПРОСТРАНСТВО</div>}
              <NavLink to={item.to} end={item.to === '/'} onClick={() => setOpen(false)}>
                <item.icon size={18} />
                <span>{item.label}</span>
                {item.to === '/import' && <span className="nav-plus">+</span>}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-card">
            <span className="live-dot" />
            <strong>{isSnapshotMode ? 'Режим просмотра' : 'Локальное пространство'}</strong>
            <p>{isSnapshotMode ? 'Данные настоящей демки' : 'Ваш компьютер. Ваши данные.'}</p>
          </div>
          <Link
            to={
              user
                ? `/players/${user.steam_id64}`
                : settings?.steam_id64
                  ? `/players/${settings.steam_id64}`
                  : '/settings'
            }
            className="sidebar-profile"
          >
            <span className="avatar small">
              <Target size={17} />
            </span>
            <div>
              <strong>
                {user?.display_name ??
                  (isSnapshotMode
                    ? 'Выбранный игрок'
                    : settings?.steam_id64
                      ? 'Личный профиль'
                      : 'Настройте профиль')}
              </strong>
              <span>{settings?.steam_id64 || 'Выберите SteamID64'}</span>
            </div>
            <ChevronRight size={15} />
          </Link>
          {user && <SteamSignOut />}
          <span className="sidebar-version">
            PREMIER ANALYZER <span>V 0.1</span>
          </span>
        </div>
      </aside>
      <div className="workspace">
        <div className="topbar">
          <div className="breadcrumbs">
            <Crosshair size={15} />
            <span>Пространство</span>
            <ChevronRight size={12} />
            <strong>{section}</strong>
          </div>
          <div className="topbar-actions">
            <Link className="topbar-search" to="/players">
              <Search size={16} />
              <span>Найти игрока</span>
            </Link>
            <span className={`api-status ${health.error ? 'offline' : ''}`}>
              <span className="live-dot" />
              {isSnapshotMode
                ? 'Демо-режим'
                : health.loading
                  ? 'Проверка API…'
                  : health.error
                    ? 'API недоступен'
                    : 'API подключён'}
            </span>
          </div>
        </div>
        <main>
          {isSnapshotMode && (
            <details className="viewer-banner">
              <summary>
                <Info size={15} />
                <span>Вы смотрите разбор контрольной демки</span>
                <span className="viewer-more">
                  Подробнее <ChevronRight size={14} />
                </span>
              </summary>
              <p>
                Настоящая демка Mirage из{' '}
                <a
                  className="text-link"
                  href="https://github.com/LaihoE/demoparser/blob/main/src/parser/test_demo.dem"
                  target="_blank"
                  rel="noreferrer"
                >
                  demoparser2
                </a>
                . Steam-вход, подключение CS2 и свои матчи доступны в{' '}
                <Link className="text-link" to="/connect">
                  серверной версии
                </Link>
                .
              </p>
            </details>
          )}
          {children}
        </main>
        <footer>
          <span className="footer-brand">
            <Crosshair size={14} /> Premier Analyzer <span>Факты из демо. Без AI.</span>
          </span>
          <div className="footer-links">
            <Link to="/connect">О подключении CS2</Link>
            <a href={sourceRepository} target="_blank" rel="noreferrer">
              Исходники <ArrowUpRight size={13} />
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}

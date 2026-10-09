import { isSnapshotMode } from '@/shared/config'
import { LockKeyhole, Target, ShieldCheck } from 'lucide-react'
import { useData } from '@/shared/api'
import type { Health } from '@/shared/api/contracts'
import { Gate, Title } from '@/shared/ui'
import { ProfileSettingsForm } from '@/features/configure-profile'

export function SettingsPage() {
  const health = useData<Health>('/api/health')
  return (
    <>
      <Title
        eyebrow="ПРОСТРАНСТВО / НАСТРОЙКИ"
        title="Под вашу игру"
        subtitle="Личный профиль, интерфейс и прозрачные настройки хранения."
      />
      <div className="settings-grid">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Личный профиль</h2>
              <p>Для выделения вашей статистики и обзора прогресса</p>
            </div>
            <Target size={20} />
          </div>
          <ProfileSettingsForm />
        </section>
        <div>
          <section className="panel">
            <div className="section-heading">
              <h2>Хранение и приватность</h2>
              <LockKeyhole size={20} />
            </div>
            <Gate {...health}>
              {health.data && (
                <dl className="settings-facts">
                  <div>
                    <dt>Статистика и настройки</dt>
                    <dd>
                      {isSnapshotMode
                        ? 'Публичный JSON / настройки в браузере'
                        : 'Локальная SQLite'}
                    </dd>
                  </div>
                  <div>
                    <dt>Копии демок</dt>
                    <dd>
                      {isSnapshotMode
                        ? 'Не размещены на сайте'
                        : health.data.retain_demos
                          ? 'Сохраняются'
                          : 'Удаляются после разбора'}
                    </dd>
                  </div>
                  <div>
                    <dt>Максимальный файл</dt>
                    <dd>
                      {isSnapshotMode
                        ? 'Импорт требует серверной версии'
                        : `${health.data.max_upload_bytes / 1024 / 1024} МБ`}
                    </dd>
                  </div>
                  <div>
                    <dt>Парсер</dt>
                    <dd>demoparser2 {health.data.parser_version}</dd>
                  </div>
                  <div>
                    <dt>Внешние запросы</dt>
                    <dd>
                      {isSnapshotMode
                        ? 'Только статические файлы сайта'
                        : 'Steam при входе и синхронизации'}
                    </dd>
                  </div>
                </dl>
              )}
            </Gate>
            <p className="muted tiny">
              Лимиты и хранение демок меняются в конфигурации backend. Инструкции — в README
              проекта.
            </p>
          </section>
          <section className="panel ai-panel">
            <span className="tag subtle">
              <ShieldCheck size={12} /> БЕЗ AI
            </span>
            <h2>Понятные наблюдения без модели</h2>
            <p>
              В MVP работают проверяемые правила и сравнение с собственной историей. Интеграция
              внешнего AI не включена: расчёт метрик выполняется локально без AI-ключей.
            </p>
          </section>
        </div>
      </div>
    </>
  )
}

import type { CS2Connection } from '@/shared/api/contracts'
export const isSyncPending = (data: CS2Connection) => ['queued', 'syncing'].includes(data.status)
export const connectionStatus = (status: string) =>
  ({
    disconnected: 'Не подключено',
    idle: 'Готово',
    queued: 'В очереди',
    syncing: 'Получаем и разбираем матчи',
    configuration_required: 'Нужна настройка сервера',
    auth_error: 'Проверьте код доступа',
    rate_limited: 'Лимит запросов Steam',
    error: 'Ошибка синхронизации',
    partial: 'Часть матчей недоступна',
    waiting_replay: 'Ожидаем демки',
    pending: 'Остались матчи для загрузки',
  })[status] ?? status

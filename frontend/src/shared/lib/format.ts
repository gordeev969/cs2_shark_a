export function fmt(value: number | null | undefined, digits = 1): string {
  return value == null
    ? 'нет данных'
    : value.toLocaleString('ru-RU', { maximumFractionDigits: digits })
}
export function date(value: string): string {
  return new Date(value).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

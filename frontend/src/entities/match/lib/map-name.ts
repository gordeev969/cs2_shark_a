export function mapName(value: string | null): string {
  return value
    ? value.replace(/^de_/, '').replace(/^./, (s) => s.toUpperCase())
    : 'Карта неизвестна'
}

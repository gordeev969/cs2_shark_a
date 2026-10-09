export function Avatar({ name, small = false }: { name: string; small?: boolean }) {
  return <span className={`avatar ${small ? 'small' : ''}`}>{name.slice(0, 2).toUpperCase()}</span>
}

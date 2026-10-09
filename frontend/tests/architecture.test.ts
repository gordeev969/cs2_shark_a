import { describe, expect, it } from 'vitest'
import { Linter } from 'eslint'
import rule from '../scripts/fsd-rule.js'

function lint(source: string, filename = '/project/src/pages/matches/ui/View.js') {
  const linter = new Linter({ cwd: '/project' })
  return linter.verify(
    source,
    [
      {
        plugins: { fsd: { rules: { architecture: rule } } },
        rules: { 'fsd/architecture': 'error' },
      },
    ],
    { filename },
  )
}

describe('FSD import boundaries', () => {
  it('allows public APIs of lower slices', () => {
    expect(
      lint("import { X } from '@/features/import-demo'; import { Y } from '@/entities/match';"),
    ).toHaveLength(0)
  })
  it('blocks upward imports', () => {
    expect(
      lint("import { X } from '@/pages/matches'", '/project/src/entities/match/ui/Table.js')[0]
        .messageId,
    ).toBe('upward')
  })
  it('blocks neighboring slices', () => {
    expect(lint("import { X } from '@/pages/players'")[0].messageId).toBe('neighbor')
  })
  it('blocks bypassing public APIs', () => {
    expect(lint("import { X } from '@/entities/match/ui/Scoreboard'")[0].messageId).toBe('private')
  })
  it('checks relative imports and dynamic imports', () => {
    expect(lint("import { X } from '../../../entities/match/ui/Scoreboard'")[0].messageId).toBe(
      'private',
    )
    expect(lint("const x = import('@/pages/players')")[0].messageId).toBe('neighbor')
  })
  it('allows internal imports and unsliced shared segments', () => {
    expect(
      lint("import { X } from '../lib/map-name'", '/project/src/entities/match/ui/Table.js'),
    ).toHaveLength(0)
    expect(
      lint("import { X } from '@/shared/api/contracts'", '/project/src/shared/ui/Gate.js'),
    ).toHaveLength(0)
  })
})

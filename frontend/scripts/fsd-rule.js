import path from 'node:path'

const layers = ['shared', 'entities', 'features', 'widgets', 'pages', 'app']
const sliced = new Set(['entities', 'features', 'widgets', 'pages'])

function location(filename) {
  const segments = filename.replaceAll('\\', '/').split('/src/').at(-1).split('/')
  return { layer: segments[0], slice: segments[1] }
}

export default {
  meta: {
    type: 'problem',
    schema: [],
    messages: {
      upward: 'FSD: {{from}} cannot import the higher layer {{to}}.',
      neighbor: 'FSD: slices on the same layer must not import each other ({{from}} → {{to}}).',
      private: 'FSD: import another slice through its public index.ts API, not {{source}}.',
    },
  },
  create(context) {
    const filename = context.filename
    if (!filename.replaceAll('\\', '/').includes('/src/')) return {}
    const from = location(filename)
    if (!layers.includes(from.layer)) return {}

    function check(node, value) {
      if (typeof value !== 'string' || !(value.startsWith('@/') || value.startsWith('.'))) return
      const target = value.startsWith('@/')
        ? filename.split('/src/')[0] + '/src/' + value.slice(2)
        : path.resolve(path.dirname(filename), value)
      const to = location(target)
      if (!layers.includes(to.layer)) return
      if (layers.indexOf(to.layer) > layers.indexOf(from.layer)) {
        context.report({ node, messageId: 'upward', data: { from: from.layer, to: to.layer } })
        return
      }
      if (sliced.has(from.layer) && from.layer === to.layer && from.slice !== to.slice) {
        context.report({ node, messageId: 'neighbor', data: { from: from.slice, to: to.slice } })
        return
      }
      const sameSlice = from.layer === to.layer && from.slice === to.slice
      const parts = target.replaceAll('\\', '/').split('/src/').at(-1).split('/')
      if (
        sliced.has(to.layer) &&
        !sameSlice &&
        parts.length > 2 &&
        !(parts.length === 3 && /^index(?:\.[jt]sx?)?$/.test(parts[2]))
      ) {
        context.report({ node, messageId: 'private', data: { source: value } })
      }
    }
    return {
      ImportDeclaration: (node) => check(node, node.source.value),
      ExportNamedDeclaration: (node) => {
        if (node.source) check(node, node.source.value)
      },
      ExportAllDeclaration: (node) => check(node, node.source.value),
      ImportExpression: (node) => check(node, node.source.value),
    }
  },
}

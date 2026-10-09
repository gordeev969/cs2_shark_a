import { Title } from '@/shared/ui'
import { DemoImport } from '@/features/import-demo'
export function ImportPage() {
  return (
    <>
      <Title
        eyebrow="БИБЛИОТЕКА / ИМПОРТ"
        title="Разберите новый матч"
        subtitle="Одна демка — полный отчёт по всем доступным участникам."
      />
      <DemoImport />
    </>
  )
}

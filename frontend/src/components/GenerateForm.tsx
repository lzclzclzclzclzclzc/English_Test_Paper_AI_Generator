import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import type { RemediationHandoff } from '@/types/app'
import type { GenerationMode } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Textarea } from '@/components/ui/textarea'

const generateSchema = z.object({
  user_query: z
    .string()
    .min(1, '先描述一下你想要的试卷')
    .max(2000, '需求描述最多 2000 字'),
  mode: z.enum(['fresh', 'remediation', 'review']),
})

export type GenerateFormValues = z.infer<typeof generateSchema>

const SUGGESTIONS = [
  '来 5 道现在完成时的选择题',
  '来 4 道词形转换题',
  '来 3 道句子改写题',
] as const

const MODES: Array<{ value: GenerationMode; label: string; hint: string }> = [
  { value: 'fresh', label: '新生成', hint: '按描述出全新一卷' },
  { value: 'remediation', label: '错题巩固', hint: '针对上一卷错题' },
  { value: 'review', label: '综合复习', hint: '基于近 30 天答题记录' },
]

interface GenerateFormProps {
  remediation: RemediationHandoff | null
  onDismissRemediation: () => void
  onSubmit: (values: GenerateFormValues) => void
  isPending: boolean
  /** ai.parser_failed / ai.no_candidate 的表单内提示 */
  serverError: string | null
}

/** 生成输入条（Spec F § 5）：ink 描边输入区 + 内嵌按钮 + 建议 chips + 模式选择。 */
export function GenerateForm({
  remediation,
  onDismissRemediation,
  onSubmit,
  isPending,
  serverError,
}: GenerateFormProps) {
  const form = useForm<GenerateFormValues>({
    resolver: zodResolver(generateSchema),
    defaultValues: {
      user_query: '',
      mode: remediation ? 'remediation' : 'fresh',
    },
  })
  const mode = form.watch('mode')

  return (
    <form className="flex flex-col gap-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
      {remediation && (
        <div className="flex items-center justify-between rounded-md border border-[#d8e0ea] bg-ink-wash px-4 py-2.5 text-[13px] text-ink">
          <span>
            已带入 {remediation.wrongItems.length} 道错题（来自〈{remediation.sourcePaperTitle}〉）
          </span>
          <button
            type="button"
            className="ml-3 text-ink/60 hover:text-ink"
            aria-label="放弃错题巩固"
            onClick={onDismissRemediation}
          >
            ✕
          </button>
        </div>
      )}

      {/* 输入条：1.5px ink 边框、内嵌按钮 */}
      <div className="flex items-end gap-2 rounded-lg border-[1.5px] border-ink bg-sheet p-2 shadow-[0_2px_8px_rgba(30,58,95,.08)]">
        <Textarea
          rows={3}
          placeholder="例如：给我出 20 道八年级下册被动语态的选择题"
          className="min-h-16 flex-1 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0"
          {...form.register('user_query')}
        />
        <Button
          type="submit"
          disabled={isPending}
          className="mb-1 shrink-0 px-6 font-bold tracking-[4px]"
        >
          {isPending ? '正在组卷…' : '出 卷'}
        </Button>
      </div>
      {form.formState.errors.user_query && (
        <p className="-mt-2 text-xs text-wrong">{form.formState.errors.user_query.message}</p>
      )}
      {serverError && <p className="-mt-2 text-xs text-wrong">{serverError}</p>}

      {/* 建议 chips */}
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            className="rounded-full border border-line-strong bg-sheet px-3 py-1 text-xs text-text-mid transition-colors hover:border-muted-foreground hover:text-foreground"
            onClick={() => form.setValue('user_query', s, { shouldValidate: true })}
          >
            {s}
          </button>
        ))}
      </div>

      {/* 模式选择 */}
      <RadioGroup
        value={mode}
        onValueChange={(v) => form.setValue('mode', v as GenerationMode)}
        className="flex flex-wrap gap-3"
      >
        {MODES.map(({ value, label, hint }) => {
          const disabled = value === 'remediation' && !remediation
          return (
            <Label
              key={value}
              title={disabled ? '交卷后，从成绩页点「错题巩固」进入' : undefined}
              className={
                disabled
                  ? 'flex cursor-not-allowed items-center gap-2 rounded-md border border-line px-3 py-2 opacity-50'
                  : mode === value
                    ? 'flex cursor-pointer items-center gap-2 rounded-md border-[1.5px] border-ink bg-ink-wash px-3 py-2 font-medium'
                    : 'flex cursor-pointer items-center gap-2 rounded-md border border-line-strong px-3 py-2 hover:border-muted-foreground'
              }
            >
              <RadioGroupItem value={value} disabled={disabled} />
              <span className="text-[13.5px]">{label}</span>
              <span className="text-xs text-muted-foreground">{hint}</span>
            </Label>
          )
        })}
      </RadioGroup>
    </form>
  )
}

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import type { RemediationHandoff } from '@/types/app'
import type { GenerationMode } from '@/types/api'
import { cn } from '@/lib/utils'
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

      {/* 模式选择：文字下划线式，与导航栏当前页同一视觉语言（Spec F § 5） */}
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1.5 pt-1">
        <span className="text-xs text-text-mid">出卷方式</span>
        <RadioGroup
          value={mode}
          onValueChange={(v) => form.setValue('mode', v as GenerationMode)}
          className="flex w-auto flex-wrap items-baseline gap-x-5 gap-y-1.5"
        >
          {MODES.map(({ value, label }) => {
            const disabled = value === 'remediation' && !remediation
            return (
              <Label
                key={value}
                title={disabled ? '交卷后，从成绩页点「错题巩固」进入' : undefined}
                className={cn(
                  'gap-0 border-b-2 pb-1 text-[13.5px] leading-none transition-colors',
                  'has-[:focus-visible]:rounded-xs has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-4 has-[:focus-visible]:outline-ring/50',
                  disabled
                    ? 'cursor-not-allowed border-transparent font-normal text-muted-foreground/70'
                    : mode === value
                      ? 'cursor-pointer border-ink font-bold text-ink'
                      : 'cursor-pointer border-transparent font-normal text-text-mid hover:text-foreground',
                )}
              >
                <span className="sr-only">
                  <RadioGroupItem value={value} disabled={disabled} />
                </span>
                {/* 隐形加粗占位：选中加粗时整行不跳动 */}
                <span className="flex flex-col">
                  {label}
                  <span aria-hidden className="invisible h-0 select-none font-bold">
                    {label}
                  </span>
                </span>
              </Label>
            )
          })}
        </RadioGroup>
        <span className="text-xs text-text-mid">
          —— {MODES.find((m) => m.value === mode)?.hint}
        </span>
      </div>
    </form>
  )
}

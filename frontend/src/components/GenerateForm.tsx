import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

const generateSchema = z.object({
  user_query: z
    .string()
    .min(1, '先描述一下你想要的试卷')
    .max(2000, '需求描述最多 2000 字'),
})

export type GenerateFormValues = z.infer<typeof generateSchema>

const SUGGESTIONS = [
  '来 5 道现在完成时的选择题',
  '来 4 道词形转换题',
  '来 3 道句子改写题',
] as const

interface GenerateFormProps {
  onSubmit: (values: GenerateFormValues) => void
  isPending: boolean
  /** ai.parser_failed / ai.no_candidate 的表单内提示 */
  serverError: string | null
  /** 非会员的免费次数提示；会员传 null 不显示 */
  quotaNotice: string | null
}

/**
 * 生成输入条（Spec F § 5）：ink 描边输入区 + 内嵌按钮 + 建议 chips。
 * 首页只做新生成（fresh）；错题巩固 / 综合复习入口在「错题复习」页。
 */
export function GenerateForm({ onSubmit, isPending, serverError, quotaNotice }: GenerateFormProps) {
  const form = useForm<GenerateFormValues>({
    resolver: zodResolver(generateSchema),
    defaultValues: { user_query: '' },
  })

  return (
    <form className="flex flex-col gap-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
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
      {quotaNotice && <p className="-mt-2 text-xs text-text-mid">{quotaNotice}</p>}

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

      <p className="text-xs text-muted-foreground">
        想练错题或综合复习？去{' '}
        <Link to="/review" className="text-ink underline underline-offset-2">
          错题复习
        </Link>
      </p>
    </form>
  )
}

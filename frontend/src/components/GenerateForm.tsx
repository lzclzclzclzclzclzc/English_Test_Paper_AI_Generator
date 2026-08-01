import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'

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
 * 生成表单（handoff 第 4 屏）：44rem textarea（focus 边框转赤陶）+
 * 建议 chips + 主按钮「生成试卷」+ 右侧状态小字。
 * 首页只做新生成（fresh）；错题巩固 / 综合复习入口在「错题本」页。
 */
export function GenerateForm({ onSubmit, isPending, serverError, quotaNotice }: GenerateFormProps) {
  const form = useForm<GenerateFormValues>({
    resolver: zodResolver(generateSchema),
    defaultValues: { user_query: '' },
  })

  return (
    <form className="flex max-w-[44rem] flex-col gap-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <textarea
        rows={4}
        placeholder="来 12 道现在完成时的单项选择，中等难度，最好带点时间状语的辨析"
        className="w-full resize-none rounded-[3px] border border-ink-20 bg-transparent px-4 py-3 text-[16px] leading-[1.8] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent"
        {...form.register('user_query')}
      />
      {form.formState.errors.user_query && (
        <p className="-mt-3 text-[12px] text-accent">{form.formState.errors.user_query.message}</p>
      )}
      {serverError && <p className="-mt-3 text-[12px] text-accent">{serverError}</p>}

      {/* 建议 chips：细线边小方角，hover 转赤陶 */}
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            className="rounded-sm border border-hairline px-3 py-1 text-[12.5px] text-muted-ink transition-colors hover:border-accent hover:bg-tint hover:text-accent"
            onClick={() => form.setValue('user_query', s, { shouldValidate: true })}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={isPending}
          className="rounded-sm border border-accent bg-wash px-8 py-3 text-[16px] tracking-[0.05em] text-ink transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
        >
          {isPending ? '生成中…' : '生成试卷'}
        </button>
        <span className="text-[12.5px] text-quiet">
          {isPending ? '生成中，请勿关闭页面' : '通常 4–6 秒'}
        </span>
      </div>

      {quotaNotice && <p className="text-[12px] text-quiet">{quotaNotice}</p>}

      <p className="text-[12.5px] text-quiet">
        想练错题或综合复习？去{' '}
        <Link to="/review" className="text-accent underline underline-offset-2">
          错题本
        </Link>
      </p>
    </form>
  )
}

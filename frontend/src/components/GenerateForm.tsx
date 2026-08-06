import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { FAMILY_CHIP_CLASS } from '@/lib/kp'
import type { TypeFamily } from '@/lib/kp'
import { PATHS } from '@/lib/paths'

const generateSchema = z.object({
  user_query: z
    .string()
    .min(1, '先描述一下你想要的试卷')
    .max(2000, '需求描述最多 2000 字'),
})

export type GenerateFormValues = z.infer<typeof generateSchema>

/** 题型 chips：点击往输入框追加「N 道××」，可连点组一份混合卷（覆盖题库全部 9 种题型）。
    分科色（Spec F v2.2）：语法 = 赭黄、听力 = 靛蓝、阅读 = 墨青。 */
const TYPE_CHIPS: ReadonlyArray<{ label: string; n: number; family: TypeFamily }> = [
  { label: '单项选择', n: 5, family: 'grammar' },
  { label: '词形转换', n: 4, family: 'grammar' },
  { label: '句子改写', n: 3, family: 'grammar' },
  { label: '听力选择', n: 3, family: 'listening' },
  { label: '听力判断', n: 4, family: 'listening' },
  { label: '听力填词', n: 3, family: 'listening' },
  { label: '阅读理解', n: 3, family: 'reading' },
  { label: '完形填空', n: 3, family: 'reading' },
  { label: '阅读首字母填空', n: 1, family: 'reading' },
]

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
        placeholder="来 12 道现在完成时的单项选择，再配 3 道听力填词——也可以点下面的题型标签组卷"
        className="w-full resize-none rounded-[3px] border border-ink-20 bg-transparent px-4 py-3 text-[16px] leading-[1.8] text-ink outline-none transition-colors placeholder:text-quiet focus:border-accent"
        {...form.register('user_query')}
      />
      {form.formState.errors.user_query && (
        <p className="-mt-3 text-[12px] text-accent">{form.formState.errors.user_query.message}</p>
      )}
      {serverError && <p className="-mt-3 text-[12px] text-accent">{serverError}</p>}

      {/* 题型 chips：细线边小方角，hover 转赤陶；点击追加「N 道××」，可连点组混合卷 */}
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-ui text-[12px] text-quiet">点选题型：</span>
        {TYPE_CHIPS.map(({ label, n, family }) => (
          <button
            key={label}
            type="button"
            className={`rounded-sm border px-3 py-1 font-ui text-[12.5px] font-[550] transition-colors ${FAMILY_CHIP_CLASS[family]}`}
            onClick={() => {
              const cur = form.getValues('user_query').trim()
              const seg = `${n} 道${label}`
              form.setValue('user_query', cur === '' ? `来 ${seg}` : `${cur}、${seg}`, {
                shouldValidate: true,
              })
            }}
          >
            {label}
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
        <Link to={PATHS.review} className="text-accent underline underline-offset-2">
          错题本
        </Link>
      </p>
    </form>
  )
}

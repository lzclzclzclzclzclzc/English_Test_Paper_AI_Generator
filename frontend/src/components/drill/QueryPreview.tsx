import { composeQuery, validateCompose, type ComposeInput } from '@/lib/composeQuery'

interface QueryPreviewProps {
  input: ComposeInput
}

/**
 * 拼句预览：把结构化选择即将拼成的 user_query 原句亮给用户看
 * （所见即所发），validateCompose 的 warn / error 跟在句子下方。
 */
export function QueryPreview({ input }: QueryPreviewProps) {
  const issues = validateCompose(input)

  return (
    <div className="flex flex-col gap-2 border-t border-hairline pt-4">
      <span className="font-ui text-[11px] font-bold tracking-[0.14em] text-quiet">
        将向 AI 发送
      </span>
      <p className="text-[15px] leading-[1.9] text-ink">「{composeQuery(input)}」</p>
      {issues.map((issue) => (
        <p
          key={issue.code}
          className={
            issue.level === 'error' ? 'text-[12px] text-accent' : 'text-[12px] text-quiet'
          }
        >
          {issue.message}
        </p>
      ))}
    </div>
  )
}

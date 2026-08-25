import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { CreditHint } from '@/components/CreditHint'
import { CountSelector } from '@/components/drill/CountSelector'
import { KpPicker } from '@/components/drill/KpPicker'
import { IntensityPicker } from '@/components/drill/IntensityPicker'
import { TopicInput } from '@/components/drill/TopicInput'
import { QueryPreview } from '@/components/drill/QueryPreview'
import { useCredits } from '@/hooks/useCredits'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { composeQuery, validateCompose, type ComposeInput, type Intensity } from '@/lib/composeQuery'
import { INTENSITY_ACTION } from '@/lib/creditsActions'
import type { DrillConfig } from '@/lib/drillConfig'
import { FAMILY_LABELS, FAMILY_TEXT_CLASS } from '@/lib/kp'
import { PATHS } from '@/lib/paths'
import { Button } from '@/components/ui/button'

interface DrillPageTemplateProps {
  config: DrillConfig
}

/**
 * 题型专项页模板：一个模板消费 9 份 DrillConfig（见 lib/drillConfig）。
 * 结构化选择 → composeQuery 确定性拼句 → 走一句话出卷同一条 fresh 通道。
 */
export function DrillPageTemplate({ config }: DrillPageTemplateProps) {
  const [count, setCount] = useState<number>(config.countPresets[0] ?? 5)
  const [kpIds, setKpIds] = useState<string[]>([])
  const [intensity, setIntensity] = useState<Intensity>(
    'locked' in config.intensity ? config.intensity.locked : 'light',
  )
  const [topic, setTopic] = useState('')
  const [serverError, setServerError] = useState<string | null>(null)

  const { generate, guard, isPending } = useGeneratePaper(setServerError, `drill:${config.slug}`)
  const { price } = useCredits()
  const kpQuery = useKnowledgePoints()

  // kp id → level2 中文名（composeQuery 拼句用名称，Parser 靠名称/alias 识别）
  const kpNames = kpIds
    .map((id) => kpQuery.data?.find((kp) => kp.id === id)?.level2)
    .filter((name): name is string => Boolean(name))

  const input: ComposeInput = {
    entries: [{ type: config.type, count, kps: kpNames }],
    intensity,
    ...(config.supportsTopic ? { topic } : {}),
  }
  const hasError = validateCompose(input).some((i) => i.level === 'error')
  // 预估价：主题非空会被 composeQuery 升为全新出题（fresh）
  const effectiveIntensity: Intensity = config.supportsTopic && topic.trim() ? 'fresh' : intensity
  const estimatedCost = price(INTENSITY_ACTION[effectiveIntensity], count)

  const handleSubmit = () => {
    setServerError(null)
    if (!guard(estimatedCost)) return
    generate({ user_query: composeQuery(input), mode: 'fresh' })
  }

  return (
    <div className="max-w-[52rem]">
      <PageHeader
        title={config.label}
        intro={
          <>
            <span
              className={`mb-2 block font-ui text-[11px] font-bold tracking-[0.14em] ${FAMILY_TEXT_CLASS[config.family]}`}
            >
              {config.family.toUpperCase()} · {FAMILY_LABELS[config.family]}专项 ·{' '}
              {config.bankLabel}
            </span>
            {config.intro}
          </>
        }
      />

      <div className="flex flex-col gap-10">
        <CountSelector
          presets={config.countPresets}
          max={config.maxCount}
          unit={config.unit}
          unitHint={config.unitHint}
          value={count}
          onChange={setCount}
        />

        {config.supportsKp && <KpPicker type={config.type} value={kpIds} onChange={setKpIds} />}

        <IntensityPicker config={config.intensity} value={intensity} onChange={setIntensity} />

        {config.supportsTopic && (
          <TopicInput value={topic} onChange={setTopic} disabled={intensity === 'original'} />
        )}

        <QueryPreview input={input} />

        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-4">
            <Button
              size="lg"
              type="button"
              disabled={isPending || hasError}
              onClick={handleSubmit}
            >
              {isPending ? '生成中…' : '生成练习'}
            </Button>
            <span className="font-ui text-[12.5px] text-quiet">
              {isPending ? '生成中，请勿关闭页面' : '通常 4–6 秒'}
            </span>
            <CreditHint action={INTENSITY_ACTION[effectiveIntensity]} cost={estimatedCost} />
          </div>
          {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
        </div>

        {isPending && <PipelineProgress />}

        <div className="flex flex-col gap-1.5">
          <p className="text-[12.5px] text-quiet">
            想混合多种题型？去{' '}
            <Link to={PATHS.practiceCustom} className="text-accent underline underline-offset-2">
              自选组卷
            </Link>
            ，或{' '}
            <Link to={PATHS.generate} className="text-accent underline underline-offset-2">
              一句话描述
            </Link>
          </p>
          {config.family === 'listening' && (
            <p className="text-[12.5px] text-quiet">听力由浏览器朗读，建议戴耳机</p>
          )}
        </div>
      </div>
    </div>
  )
}

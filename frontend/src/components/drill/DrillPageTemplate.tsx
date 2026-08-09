import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { PipelineProgress } from '@/components/PipelineProgress'
import { UpgradeDialog } from '@/components/UpgradeDialog'
import { CountSelector } from '@/components/drill/CountSelector'
import { KpPicker } from '@/components/drill/KpPicker'
import { IntensityPicker } from '@/components/drill/IntensityPicker'
import { TopicInput } from '@/components/drill/TopicInput'
import { QueryPreview } from '@/components/drill/QueryPreview'
import { useGeneratePaper } from '@/hooks/useGeneratePaper'
import { useKnowledgePoints } from '@/hooks/useKnowledgePoints'
import { composeQuery, validateCompose, type ComposeInput, type Intensity } from '@/lib/composeQuery'
import type { DrillConfig } from '@/lib/drillConfig'
import { FAMILY_LABELS, FAMILY_TEXT_CLASS } from '@/lib/kp'
import { generateQuotaNotice } from '@/lib/quota'
import { PATHS } from '@/lib/paths'

/** 非会员点「真题原样」档时的升级文案 */
const ORIGINAL_LOCK_REASON = '真题原卷是会员功能：整卷使用中考真题原题，不做改动。'

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
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null)

  const { generate, guard, isPending, locked, freeRemaining } = useGeneratePaper(setServerError)
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
  const quotaNotice = generateQuotaNotice(locked, freeRemaining)

  const handleSubmit = () => {
    setServerError(null)
    const reason = guard('fresh')
    if (reason) {
      setUpgradeReason(reason)
      return
    }
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

        <IntensityPicker
          config={config.intensity}
          value={intensity}
          onChange={setIntensity}
          memberLocked={locked}
          onLockedIntensity={() => setUpgradeReason(ORIGINAL_LOCK_REASON)}
        />

        {config.supportsTopic && (
          <TopicInput value={topic} onChange={setTopic} disabled={intensity === 'original'} />
        )}

        <QueryPreview input={input} />

        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-4">
            <button
              type="button"
              disabled={isPending || hasError}
              className="rounded-sm border border-accent bg-wash px-8 py-3 font-ui text-[16px] tracking-[0.05em] text-ink transition-colors hover:text-accent disabled:pointer-events-none disabled:opacity-60"
              onClick={handleSubmit}
            >
              {isPending ? '生成中…' : '生成练习'}
            </button>
            <span className="font-ui text-[12.5px] text-quiet">
              {isPending ? '生成中，请勿关闭页面' : '通常 4–6 秒'}
            </span>
          </div>
          {serverError && <p className="text-[12px] text-accent">{serverError}</p>}
          {quotaNotice && <p className="font-ui text-[12px] tabular-nums text-quiet">{quotaNotice}</p>}
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

      <UpgradeDialog reason={upgradeReason} onClose={() => setUpgradeReason(null)} />
    </div>
  )
}

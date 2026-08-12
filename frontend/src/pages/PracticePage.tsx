import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/PageHeader'
import { DRILL_FAMILIES } from '@/lib/drillConfig'
import { FAMILY_LABELS, FAMILY_TEXT_CLASS, type TypeFamily } from '@/lib/kp'
import { PATHS } from '@/lib/paths'

/** 族色细线（border-b 30% 不透明度）——Tailwind 需要写死类名 */
const FAMILY_BORDER_CLASS: Record<TypeFamily, string> = {
  grammar: 'border-grammar/30',
  listening: 'border-listening/30',
  reading: 'border-reading/30',
  writing: 'border-writing/30',
}

/** 族 → tile 彩色变体类 */
const FAMILY_TILE_CLASS: Record<TypeFamily, string> = {
  grammar: 'tile--grammar',
  listening: 'tile--listening',
  reading: 'tile--reading',
  writing: 'tile--writing',
}

const FAMILY_DESC: Record<TypeFamily, string> = {
  grammar: '打牢语法基本功，三类题占中考笔试大头',
  listening: 'AI 朗读，可反复听',
  reading: '长文、完形与首字母，按篇成组',
  writing: '成篇写作，AI 从内容 / 语言 / 组织三维批改评分',
}

/**
 * 练习中心 hub（纯导航页）：十大题型按语法/听力/阅读/写作分区，
 * 每族一组彩色方块（分科色）。页脚留自选组卷入口。
 */
export function PracticePage() {
  return (
    <div className="max-w-[56rem]">
      <PageHeader
        title="练习中心"
        intro="十大题型按语法、听力、阅读、写作分科组织——选一类开始专项练习，或去自选组卷混合搭配。"
      />

      <div className="flex flex-col gap-12">
        {/* 分科分区：族标题 + 族色细线 + 彩色方块网格 */}
        {DRILL_FAMILIES.map(({ family, configs }) => (
          <section key={family}>
            <div className={cn('border-b pb-2', FAMILY_BORDER_CLASS[family])}>
              <span
                className={cn(
                  'font-ui text-[11px] font-bold tracking-[0.14em]',
                  FAMILY_TEXT_CLASS[family],
                )}
              >
                {family.toUpperCase()} · {FAMILY_LABELS[family]}
              </span>
            </div>
            <p className="mb-4 mt-2.5 text-[13.5px] text-muted-ink">{FAMILY_DESC[family]}</p>
            <div className="tile-grid" style={{ ['--tile-cols' as string]: '3' }}>
              {configs.map((config) => (
                <Link
                  key={config.slug}
                  to={PATHS.practiceType(config.slug)}
                  className={cn('tile', FAMILY_TILE_CLASS[family])}
                >
                  <span className="tile-title">{config.label}</span>
                  <span className="tile-desc">{config.bankLabel}</span>
                  <span className="tile-idx mt-1">开始 →</span>
                </Link>
              ))}
            </div>
            {/* 主题×题型的入口指引：主题出卷已独立成页 */}
            {family === 'grammar' && (
              <div className="mt-4 flex flex-wrap items-baseline gap-x-2 px-1 font-ui text-[13px]">
                <span className="text-quiet">想按话题练语法？</span>
                <Link
                  to={PATHS.themes}
                  className="text-quiet transition-colors hover:text-accent"
                >
                  去主题出卷 →
                </Link>
              </div>
            )}
          </section>
        ))}

        {/* 页脚：自选组卷入口 + 词汇预告 */}
        <div className="divide-y divide-ink-10 border-t border-hairline">
          <Link
            to={PATHS.practiceCustom}
            className="group flex items-baseline gap-3 px-2 py-4 transition-colors hover:bg-tint"
          >
            <span className="font-ui text-[14.5px] text-ink">自选组卷</span>
            <span className="text-[12px] text-quiet">— 像点菜一样自由配比</span>
            <span className="ml-auto shrink-0 font-ui text-[13px] text-quiet transition-colors group-hover:text-accent">
              →
            </span>
          </Link>
          <Link
            to={PATHS.vocabulary}
            className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-2 py-4 transition-colors hover:bg-tint"
          >
            <span className="font-ui text-[14.5px] text-ink">背单词</span>
            <span className="text-[12px] text-quiet">— 国家核心 1600 词，间隔重复安排复习节奏 →</span>
          </Link>
        </div>
      </div>
    </div>
  )
}

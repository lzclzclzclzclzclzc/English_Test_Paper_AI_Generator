import {
  FAMILY_CHIP_CLASS,
  FAMILY_LABELS,
  FAMILY_TEXT_CLASS,
  TYPE_LABELS,
  type TypeFamily,
} from '@/lib/kp'

interface TypeRow {
  id: string
  desc: string
}

interface FamilyColumn {
  family: TypeFamily
  kicker: string
  rows: TypeRow[]
  footnote?: string
}

/* 题型名一律从 TYPE_LABELS 取,这里只补每型一句描述。 */
const COLUMNS: readonly FamilyColumn[] = [
  {
    family: 'grammar',
    kicker: 'GRAMMAR',
    rows: [
      { id: 'single_choice', desc: '时态、从句、固定搭配，真题库最厚的一摞。' },
      { id: 'word_form', desc: '给词根写对形态，考的是语法功底。' },
      { id: 'sentence_rewriting', desc: '改被动、改感叹、连词成句，一空一分。' },
    ],
  },
  {
    family: 'listening',
    kicker: 'LISTENING',
    rows: [
      { id: 'listening_single_choice', desc: '听短对话选答案，AI 语音朗读，可反复播放。' },
      { id: 'listening_true_false', desc: '听短文判断正误，练抓关键信息。' },
      { id: 'listening_fill_blank', desc: '边听边写，拼写与听力一起过关。' },
    ],
    footnote: '听力题配 AI 朗读，浏览器直接播放，无需下载。',
  },
  {
    family: 'reading',
    kicker: 'READING',
    rows: [
      { id: 'reading_longtext_single_choice', desc: '长文配题，主旨题细节题都有。' },
      { id: 'cloze_single_choice', desc: '上下文里选词，语感与逻辑并重。' },
      { id: 'reading_first_blank', desc: '中考阅读最难一关，给首字母补全词。' },
    ],
  },
]

/* 族色 30% 细线:类名必须是静态字面量,Tailwind 才收得进产物。 */
const FAMILY_RULE_CLASS: Record<TypeFamily, string> = {
  grammar: 'border-grammar/30',
  listening: 'border-listening/30',
  reading: 'border-reading/30',
  writing: 'border-writing/30',
}

/** #types 九大题型:三列一族(族色列头细线),行 = 题型 chip + 一句描述。 */
export function TypeGrid() {
  return (
    <section id="types" className="scroll-mt-20 border-t border-hairline py-14">
      <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">
        中考考什么，这里就练什么
      </h2>
      <p className="mt-3 max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
        九大题型按语法、听力、阅读三科组织，覆盖上海中考卷面的纯文字与听力部分。
      </p>
      <div className="mt-10 grid grid-cols-3 gap-x-12 gap-y-10 max-md:grid-cols-1">
        {COLUMNS.map((col) => (
          <div key={col.family}>
            <p
              className={`border-b pb-2.5 font-ui text-[11px] font-bold tracking-[0.1em] ${FAMILY_TEXT_CLASS[col.family]} ${FAMILY_RULE_CLASS[col.family]}`}
            >
              {col.kicker} · {FAMILY_LABELS[col.family]}
            </p>
            <div>
              {col.rows.map((row) => (
                <div
                  key={row.id}
                  className="flex flex-col items-start gap-2 border-b border-hairline py-4 last:border-b-0"
                >
                  <span
                    className={`rounded-sm border px-3 py-1 font-ui text-[12.5px] ${FAMILY_CHIP_CLASS[col.family]}`}
                  >
                    {TYPE_LABELS[row.id] ?? row.id}
                  </span>
                  <p className="text-[14px] leading-[1.8] text-muted-ink">{row.desc}</p>
                </div>
              ))}
            </div>
            {col.footnote && <p className="mt-3 text-[12.5px] text-quiet">{col.footnote}</p>}
          </div>
        ))}
      </div>
    </section>
  )
}

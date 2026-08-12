import { TYPE_LABELS } from '@/lib/kp'

interface TypeRow {
  id: string
  tnum: string
  desc: string
}
interface SubjectBlock {
  cn: string
  en: string
  note?: string
  three: boolean
  rows: TypeRow[]
}

/* 题型名从 TYPE_LABELS 取,这里只补编号与一句描述。 */
const BLOCKS: readonly SubjectBlock[] = [
  {
    cn: '语法', en: 'Grammar', three: false,
    rows: [
      { id: 'single_choice', tnum: 'G · 01', desc: '时态、从句、固定搭配，真题库最厚的一摞。' },
      { id: 'word_form', tnum: 'G · 02', desc: '给词根写对形态，考的是语法功底。' },
      { id: 'sentence_rewriting', tnum: 'G · 03', desc: '改被动、改感叹、连词成句，一空一分。' },
      { id: 'writing', tnum: 'G · 04', desc: '成篇写作，AI 从内容 / 语言 / 组织三维批改评分。' },
    ],
  },
  {
    cn: '听力', en: 'Listening', three: true,
    note: '听力题配 AI 朗读，浏览器直接播放，无需下载。',
    rows: [
      { id: 'listening_single_choice', tnum: 'L · 01', desc: '听短对话选答案，AI 语音朗读，可反复播放。' },
      { id: 'listening_true_false', tnum: 'L · 02', desc: '听短文判断正误，练抓关键信息。' },
      { id: 'listening_fill_blank', tnum: 'L · 03', desc: '边听边写，拼写与听力一起过关。' },
    ],
  },
  {
    cn: '阅读', en: 'Reading', three: true,
    rows: [
      { id: 'reading_longtext_single_choice', tnum: 'R · 01', desc: '长文配题，主旨题细节题都有。' },
      { id: 'cloze_single_choice', tnum: 'R · 02', desc: '上下文里选词，语感与逻辑并重。' },
      { id: 'reading_first_blank', tnum: 'R · 03', desc: '中考阅读最难一关，给首字母补全词。' },
    ],
  },
]

/** #types 题型网格:三科分块,每块题型卡(4/3/3),族色列头细线。 */
export function TypeGrid() {
  return (
    <section className="section" id="types">
      <div className="l-wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow-row"><span className="idx">TYPES</span><hr className="hairline" /></div>
            <h2 className="h-sec">中考考什么，<br />这里就练什么</h2>
          </div>
          <p className="lead">十大题型按语法、听力、阅读三科组织，覆盖上海中考卷面的纯文字与听力部分。</p>
        </div>

        {BLOCKS.map((block, bi) => (
          <div className={`subj-block${bi === BLOCKS.length - 1 ? ' last' : ''}`} key={block.en}>
            <div className="subj-head">
              <span className="cn">{block.cn}</span>
              <span className="en">{block.en}</span>
              {block.note && <span className="note">{block.note}</span>}
            </div>
            <div className={`type-grid${block.three ? ' three' : ''}`}>
              {block.rows.map((row) => (
                <div className="tcard" key={row.id}>
                  <div className="tnum">{row.tnum}</div>
                  <h4>{TYPE_LABELS[row.id] ?? row.id}</h4>
                  <p>{row.desc}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

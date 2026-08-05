import { describe, expect, it } from 'vitest'
import type { Paper, PaperItem, RevisedQuestion } from '@/types/api'
import {
  buildSubmission,
  formatCorrectAnswer,
  formatUserAnswer,
  getBlankKeys,
  listUnanswered,
  splitTemplateByBlanks,
} from '@/lib/answers'

const q = (over: Partial<RevisedQuestion>): RevisedQuestion => ({
  stem: null,
  question_type: 'word_form',
  options: null,
  hint: null,
  original_sentence: null,
  instruction: null,
  template: null,
  answer: [{ blank1: ['x'] }],
  solution: null,
  passage_id: null,
  passage_json: null,
  knowledge_point_ids: [],
  ...over,
})

const item = (index: number, question: RevisedQuestion): PaperItem => ({
  index,
  question,
  source_question_id: `q_${index}`,
  revision_mode: 'original',
})

const paper = (items: PaperItem[]): Paper => ({
  paper_id: 'p1',
  title: 't',
  generated_at: '2026-07-09T00:00:00Z',
  request: {
    mode: 'fresh',
    knowledge_points: [],
    question_types: [],
    total_questions: items.length,
    type_distribution: {},
    revision_intensity: 'light',
    wrong_items: [],
    user_id: null,
    review_window_days: null,
    free_text: '',
  },
  items,
  metadata: {},
})

describe('getBlankKeys', () => {
  it('单选（字符串答案）无空', () => {
    expect(getBlankKeys('B')).toEqual([])
  })
  it('多空按数字后缀排序（blank10 不排在 blank2 前）', () => {
    expect(
      getBlankKeys([{ blank10: ['j'], blank2: ['b'], blank1: ['a'] }]),
    ).toEqual(['blank1', 'blank2', 'blank10'])
  })
  it('多元素单空 dict（阅读首字母填空）汇总全部键', () => {
    expect(
      getBlankKeys([
        { blank1: ['c'] },
        { blank2: ['f'] },
        { blank3: ['i'] },
      ]),
    ).toEqual(['blank1', 'blank2', 'blank3'])
  })
  it('异常空数组兜底单空', () => {
    expect(getBlankKeys([])).toEqual(['blank1'])
  })
})

describe('splitTemplateByBlanks', () => {
  it('段数吻合时切分（2 空 → 3 段）', () => {
    expect(
      splitTemplateByBlanks('He is ________ young ________ he cannot go.', 2),
    ).toEqual(['He is ', ' young ', ' he cannot go.'])
  })
  it('真题现象：两空合成一条下划线连串 → 不匹配返回 null', () => {
    expect(splitTemplateByBlanks('This model________________me 240 yuan.', 2)).toBeNull()
  })
  it('三个下划线也算空位标记（fake engine 的 ___）', () => {
    expect(splitTemplateByBlanks('He has ___ (write) it.', 1)).toEqual([
      'He has ',
      ' (write) it.',
    ])
  })
})

describe('buildSubmission', () => {
  const p = paper([
    item(1, q({ question_type: 'single_choice', answer: 'B', options: [] })),
    item(2, q({ answer: [{ blank1: ['written'] }] })),
    item(3, q({ question_type: 'sentence_rewriting', answer: [{ blank1: ['so'], blank2: ['that'] }] })),
  ])

  it('为全部 index 各生成恰好一条（后端 422 硬约束），未答补空', () => {
    const items = buildSubmission(p, {})
    expect(items.map((i) => i.index)).toEqual([1, 2, 3])
    expect(items[0]!.user_answer).toBe('')
    expect(items[1]!.user_answer).toEqual({ blank1: '' })
    expect(items[2]!.user_answer).toEqual({ blank1: '', blank2: '' })
  })

  it('已答内容原样带出并 trim', () => {
    const items = buildSubmission(p, {
      1: 'B',
      2: { blank1: ' written ' },
      3: { blank1: 'so', blank2: 'that' },
    })
    expect(items[0]!.user_answer).toBe('B')
    expect(items[1]!.user_answer).toEqual({ blank1: 'written' })
    expect(items[2]!.user_answer).toEqual({ blank1: 'so', blank2: 'that' })
  })

  it('部分填写的多空题：缺失键补空字符串', () => {
    const items = buildSubmission(p, { 3: { blank1: 'so' } })
    expect(items[2]!.user_answer).toEqual({ blank1: 'so', blank2: '' })
  })
})

describe('listUnanswered', () => {
  const p = paper([
    item(1, q({ question_type: 'single_choice', answer: 'B', options: [] })),
    item(2, q({ question_type: 'sentence_rewriting', answer: [{ blank1: ['so'], blank2: ['that'] }] })),
  ])

  it('全未答', () => {
    expect(listUnanswered(p, {})).toEqual([1, 2])
  })
  it('多空只填一半仍算未答完', () => {
    expect(listUnanswered(p, { 1: 'A', 2: { blank1: 'so' } })).toEqual([2])
  })
  it('全答完为空', () => {
    expect(listUnanswered(p, { 1: 'A', 2: { blank1: 'so', blank2: 'that' } })).toEqual([])
  })
  it('空白字符串不算已答', () => {
    expect(listUnanswered(p, { 1: 'A', 2: { blank1: '  ', blank2: 'that' } })).toEqual([2])
  })
})

describe('formatUserAnswer', () => {
  it('字符串直出，空串标记未作答', () => {
    expect(formatUserAnswer('B')).toBe('B')
    expect(formatUserAnswer('')).toBe('（未作答）')
  })
  it('数组按序拼接', () => {
    expect(formatUserAnswer(['so', 'that'])).toBe('so；that')
  })
  it('多空字典带空位标签', () => {
    expect(formatUserAnswer({ blank2: 'that', blank1: 'so' })).toBe('空1: so；空2: that')
  })
  it('单空字典不带标签', () => {
    expect(formatUserAnswer({ blank1: 'written' })).toBe('written')
  })
})

describe('formatCorrectAnswer', () => {
  it('单选字母直出', () => {
    expect(formatCorrectAnswer('B')).toBe('B')
  })
  it('单空多候选用斜杠分隔', () => {
    expect(formatCorrectAnswer([{ blank1: ['proof', 'proofs'] }])).toBe('proof / proofs')
  })
  it('多空组合带空位标签', () => {
    expect(formatCorrectAnswer([{ blank1: ['so'], blank2: ['that'] }])).toBe(
      '空1: so；空2: that',
    )
  })
  it('多候选组合用带圈序号分组', () => {
    expect(
      formatCorrectAnswer([
        { blank1: ['so'], blank2: ['that'] },
        { blank1: ['in'], blank2: ['order'] },
      ]),
    ).toBe('① 空1: so；空2: that　② 空1: in；空2: order')
  })
  it('多元素单空 dict（阅读首字母填空）按空位顺序展示', () => {
    expect(
      formatCorrectAnswer([
        { blank1: ['concentrate'] },
        { blank2: ['fall'] },
        { blank3: ['interesting'] },
      ]),
    ).toBe('空1: concentrate；空2: fall；空3: interesting')
  })
})

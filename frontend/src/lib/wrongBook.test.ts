import { beforeEach, describe, expect, it } from 'vitest'
import type { GradeResultItem, Paper, PaperItem, RevisedQuestion } from '@/types/api'
import { loadWrongBook, recordGrade, removeEntry, toWrongItemRefs } from './wrongBook'

// vitest 跑在 node 环境：给 wrongBook 用到的 localStorage 三件套一个内存桩
const memory = new Map<string, string>()
globalThis.localStorage = {
  getItem: (k: string) => memory.get(k) ?? null,
  setItem: (k: string, v: string) => void memory.set(k, String(v)),
  removeItem: (k: string) => void memory.delete(k),
  clear: () => memory.clear(),
  key: (i: number) => [...memory.keys()][i] ?? null,
  get length() {
    return memory.size
  },
} as Storage

const U = 'user1'

function question(overrides: Partial<RevisedQuestion> = {}): RevisedQuestion {
  return {
    stem: 'Choose the correct answer.',
    question_type: 'single_choice',
    options: [
      { label: 'A', text: 'go' },
      { label: 'B', text: 'goes' },
    ],
    hint: null,
    original_sentence: null,
    instruction: null,
    template: null,
    passage_id: null,
    passage_json: null,
    answer: 'B',
    solution: null,
    passage_id: null,
    passage_json: null,
    knowledge_point_ids: ['kp_single_choice_basic'],
    ...overrides,
  }
}

function paperWith(items: Array<Partial<PaperItem> & { index: number }>): Paper {
  return {
    paper_id: 'p1',
    title: '测试卷',
    generated_at: '2026-07-19T00:00:00Z',
    request: {
      mode: 'fresh',
      knowledge_points: [],
      question_types: ['single_choice'],
      total_questions: items.length,
      type_distribution: {},
      revision_intensity: 'light',
      wrong_items: [],
      user_id: null,
      review_window_days: null,
      free_text: '',
    },
    items: items.map((it) => ({
      question: question(),
      source_question_id: `q_${it.index}`,
      revision_mode: 'light',
      ...it,
    })),
    metadata: {},
  }
}

const wrong = (index: number): GradeResultItem => ({
  index,
  user_answer: 'A',
  correct_answer: 'B',
  is_correct: false,
})
const right = (index: number): GradeResultItem => ({
  index,
  user_answer: 'B',
  correct_answer: 'B',
  is_correct: true,
})

beforeEach(() => localStorage.clear())

describe('recordGrade', () => {
  it('只收答错的题，最新在前', () => {
    recordGrade(U, paperWith([{ index: 1 }, { index: 2 }]), [wrong(1), right(2)])
    const entries = loadWrongBook(U)
    expect(entries).toHaveLength(1)
    expect(entries[0]?.sourceQuestionId).toBe('q_1')
    expect(entries[0]?.timesWrong).toBe(1)
    expect(entries[0]?.userAnswer).toBe('A')
  })

  it('同源题再错：去重、次数累加、移到最前', () => {
    recordGrade(U, paperWith([{ index: 1 }, { index: 2 }]), [wrong(1), wrong(2)])
    recordGrade(U, paperWith([{ index: 1 }]), [wrong(1)])
    const entries = loadWrongBook(U)
    expect(entries).toHaveLength(2)
    expect(entries[0]?.sourceQuestionId).toBe('q_1')
    expect(entries[0]?.timesWrong).toBe(2)
    expect(entries[1]?.timesWrong).toBe(1)
  })

  it('重做答对即清账', () => {
    recordGrade(U, paperWith([{ index: 1 }]), [wrong(1)])
    expect(loadWrongBook(U)).toHaveLength(1)
    recordGrade(U, paperWith([{ index: 1 }]), [right(1)])
    expect(loadWrongBook(U)).toHaveLength(0)
  })

  it('超过 100 条从尾部淘汰', () => {
    for (let batch = 0; batch < 6; batch++) {
      const items = Array.from({ length: 20 }, (_, i) => ({
        index: i + 1,
        source_question_id: `q_${batch * 20 + i}`,
      }))
      recordGrade(U, paperWith(items), items.map((it) => wrong(it.index)))
    }
    const entries = loadWrongBook(U)
    expect(entries).toHaveLength(100)
    // 最早一批（q_0..q_19）已被淘汰
    expect(entries.some((e) => e.sourceQuestionId === 'q_0')).toBe(false)
    expect(entries[0]?.sourceQuestionId).toBe('q_100')
  })

  it('按用户隔离', () => {
    recordGrade(U, paperWith([{ index: 1 }]), [wrong(1)])
    expect(loadWrongBook('user2')).toHaveLength(0)
  })

  it('坏 JSON 容错：视为空本继续记账', () => {
    localStorage.setItem(`mj.wrongbook.v1.${U}`, '{not json')
    recordGrade(U, paperWith([{ index: 1 }]), [wrong(1)])
    expect(loadWrongBook(U)).toHaveLength(1)
  })
})

describe('removeEntry / toWrongItemRefs', () => {
  it('移出后持久化并返回新列表', () => {
    recordGrade(U, paperWith([{ index: 1 }, { index: 2 }]), [wrong(1), wrong(2)])
    const rest = removeEntry(U, 'q_1')
    expect(rest).toHaveLength(1)
    expect(loadWrongBook(U)).toHaveLength(1)
  })

  it('映射为 remediation 请求体的 wrong_items', () => {
    recordGrade(U, paperWith([{ index: 1 }]), [wrong(1)])
    const refs = toWrongItemRefs(loadWrongBook(U))
    expect(refs).toEqual([
      { knowledge_point_ids: ['kp_single_choice_basic'], question_type: 'single_choice' },
    ])
  })
})

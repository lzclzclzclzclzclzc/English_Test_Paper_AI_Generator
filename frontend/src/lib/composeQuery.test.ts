import { describe, expect, it } from 'vitest'
import {
  MAX_QUESTIONS,
  composeQuery,
  questionsPerUnit,
  totalQuestions,
  unitOf,
  validateCompose,
} from '@/lib/composeQuery'

describe('unitOf / questionsPerUnit', () => {
  it('散题按道,篇章按篇', () => {
    expect(unitOf('single_choice')).toBe('道')
    expect(unitOf('listening_fill_blank')).toBe('道')
    expect(unitOf('reading_longtext_single_choice')).toBe('篇')
    expect(unitOf('cloze_single_choice')).toBe('篇')
    expect(unitOf('reading_first_blank')).toBe('篇')
  })
  it('阅读/完形每篇 6 题,首字母 1 篇 = 1 题', () => {
    expect(questionsPerUnit('reading_longtext_single_choice')).toBe(6)
    expect(questionsPerUnit('cloze_single_choice')).toBe(6)
    expect(questionsPerUnit('reading_first_blank')).toBe(1)
    expect(questionsPerUnit('word_form')).toBe(1)
  })
})

describe('totalQuestions(篇换算)', () => {
  it('2 篇阅读 + 1 篇完形 = 18 题', () => {
    expect(
      totalQuestions([
        { type: 'reading_longtext_single_choice', count: 2 },
        { type: 'cloze_single_choice', count: 1 },
      ]),
    ).toBe(18)
  })
  it('首字母 2 篇计 2 题', () => {
    expect(totalQuestions([{ type: 'reading_first_blank', count: 2 }])).toBe(2)
  })
})

describe('composeQuery', () => {
  it('纯题型(light 默认)= parser 示例 1 句式', () => {
    expect(composeQuery({ entries: [{ type: 'single_choice', count: 5 }] })).toBe(
      '来 5 道单项选择',
    )
  })
  it('题型 + 单个知识点', () => {
    expect(
      composeQuery({
        entries: [{ type: 'single_choice', count: 5, kps: ['现在完成时'] }],
      }),
    ).toBe('来 5 道现在完成时的单项选择')
  })
  it('多知识点用「和」连接(顿号是分段符,不混用)', () => {
    expect(
      composeQuery({
        entries: [{ type: 'single_choice', count: 8, kps: ['不定代词', '介词'] }],
      }),
    ).toBe('来 8 道不定代词和介词的单项选择')
  })
  it('多题型混合用顿号分段', () => {
    expect(
      composeQuery({
        entries: [
          { type: 'single_choice', count: 5 },
          { type: 'listening_fill_blank', count: 3 },
        ],
      }),
    ).toBe('来 5 道单项选择、3 道听力填词')
  })
  it('篇章题型按篇拼句', () => {
    expect(
      composeQuery({
        entries: [
          { type: 'reading_longtext_single_choice', count: 2 },
          { type: 'cloze_single_choice', count: 1 },
        ],
      }),
    ).toBe('来 2 篇阅读理解、1 篇完形填空')
  })
  it('original 档命中「真题/原题/不要改」触发词', () => {
    expect(
      composeQuery({
        entries: [{ type: 'single_choice', count: 10 }],
        intensity: 'original',
      }),
    ).toBe('来 10 道单项选择，全部用真题原题，不要改')
  })
  it('fresh 档复刻 parser 示例 6 的「帮我重新出」开头', () => {
    expect(
      composeQuery({
        entries: [{ type: 'single_choice', count: 10 }],
        intensity: 'fresh',
      }),
    ).toBe('帮我重新出 10 道单项选择，要全新原创的题目')
  })
  it('fresh + KP + 主题', () => {
    expect(
      composeQuery({
        entries: [{ type: 'word_form', count: 6, kps: ['动词转换为名词'] }],
        intensity: 'fresh',
        topic: '环保',
      }),
    ).toBe('帮我重新出 6 道动词转换为名词的词形转换，要全新原创的题目，主题关于环保')
  })
  it('light + 主题自动升为 fresh(情境描述必然触发 fresh)', () => {
    expect(
      composeQuery({
        entries: [{ type: 'single_choice', count: 10 }],
        topic: '校园生活',
      }),
    ).toBe('帮我重新出 10 道单项选择，要全新原创的题目，主题关于校园生活')
  })
  it('original 档丢弃主题词', () => {
    expect(
      composeQuery({
        entries: [{ type: 'single_choice', count: 10 }],
        intensity: 'original',
        topic: '环保',
      }),
    ).toBe('来 10 道单项选择，全部用真题原题，不要改')
  })
  it('非语法题型忽略 kps', () => {
    expect(
      composeQuery({
        entries: [{ type: 'listening_fill_blank', count: 5, kps: ['听力填词'] }],
      }),
    ).toBe('来 5 道听力填词')
  })
  it('count 为 0 的条目不进句子', () => {
    expect(
      composeQuery({
        entries: [
          { type: 'single_choice', count: 5 },
          { type: 'word_form', count: 0 },
        ],
      }),
    ).toBe('来 5 道单项选择')
  })
})

describe('validateCompose', () => {
  it('空输入报 error', () => {
    expect(validateCompose({ entries: [] })).toEqual([
      expect.objectContaining({ level: 'error', code: 'empty' }),
    ])
    expect(validateCompose({ entries: [{ type: 'single_choice', count: 0 }] })).toEqual([
      expect.objectContaining({ level: 'error', code: 'empty' }),
    ])
  })
  it('非整数数量报 error', () => {
    const issues = validateCompose({ entries: [{ type: 'single_choice', count: 2.5 }] })
    expect(issues.some((i) => i.code === 'count_invalid')).toBe(true)
  })
  it('6 篇完形 = 36 题,超 30 上限被拦', () => {
    const issues = validateCompose({
      entries: [{ type: 'cloze_single_choice', count: 6 }],
    })
    expect(issues).toEqual([expect.objectContaining({ level: 'error', code: 'over_cap' })])
    expect(issues[0]?.message).toContain(String(MAX_QUESTIONS))
  })
  it('恰好 30 题放行', () => {
    expect(
      validateCompose({ entries: [{ type: 'cloze_single_choice', count: 5 }] }),
    ).toEqual([])
  })
  it('original + 主题 → warn topic_dropped', () => {
    const issues = validateCompose({
      entries: [{ type: 'single_choice', count: 5 }],
      intensity: 'original',
      topic: '环保',
    })
    expect(issues).toEqual([expect.objectContaining({ level: 'warn', code: 'topic_dropped' })])
  })
  it('light + 主题 → warn topic_fresh(升档提示)', () => {
    const issues = validateCompose({
      entries: [{ type: 'single_choice', count: 5 }],
      topic: '环保',
    })
    expect(issues).toEqual([expect.objectContaining({ level: 'warn', code: 'topic_fresh' })])
  })
})

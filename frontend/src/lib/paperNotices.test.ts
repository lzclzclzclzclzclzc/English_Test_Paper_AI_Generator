import { describe, expect, it } from 'vitest'
import { buildPaperNotices } from '@/lib/paperNotices'

describe('buildPaperNotices', () => {
  it('空 metadata / 非对象 metadata 返回空', () => {
    expect(buildPaperNotices({})).toEqual([])
    expect(buildPaperNotices(null)).toEqual([])
    expect(buildPaperNotices(undefined)).toEqual([])
    expect(buildPaperNotices('oops')).toEqual([])
  })

  it('revision_failures 题号排序拼句', () => {
    expect(buildPaperNotices({ revision_failures: [5, 3] })).toEqual([
      '第 3、5 题 AI 改写未成功，已使用题库原题',
    ])
  })

  it('shortfall 与 retrieval_shortfall 都识别，已知题型翻译成中文', () => {
    expect(buildPaperNotices({ shortfall: { single_choice: 2, unknown_bucket: 1 } })).toEqual([
      '题库题量不足：单项选择缺 2 道，unknown_bucket缺 1 道',
    ])
    expect(buildPaperNotices({ retrieval_shortfall: { word_form: 3 } })).toEqual([
      '题库题量不足：词形转换缺 3 道',
    ])
  })

  it('retrieval_warnings 原样透传（去空白、丢非字符串）', () => {
    expect(
      buildPaperNotices({ retrieval_warnings: [' 知识点 kp_x 不存在，已忽略 ', 42, ''] }),
    ).toEqual(['知识点 kp_x 不存在，已忽略'])
  })

  it('形态不符时静默丢弃（容忍未知字段是契约要求）', () => {
    expect(
      buildPaperNotices({
        revision_failures: 'not-a-list',
        shortfall: [1, 2],
        retrieval_shortfall: { single_choice: 0, word_form: -1, bad: 'x' },
        retrieval_warnings: {},
        future_field: { anything: true },
      }),
    ).toEqual([])
  })

  it('多种提示并存时按 失败题 → 缺口 → 告警 顺序输出', () => {
    expect(
      buildPaperNotices({
        retrieval_warnings: ['向量检索降级为随机抽题'],
        shortfall: { sentence_rewriting: 1 },
        revision_failures: [2],
      }),
    ).toEqual([
      '第 2 题 AI 改写未成功，已使用题库原题',
      '题库题量不足：句子改写缺 1 道',
      '向量检索降级为随机抽题',
    ])
  })
})

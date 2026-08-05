import { describe, expect, it } from 'vitest'
import {
  formatVocabularyMeanings,
  isVocabularyExamplePlaceholder,
  vocabularyNextLabel,
  vocabularyPhaseLabel,
} from '@/lib/vocabularyDisplay'

describe('vocabulary display labels', () => {
  it('labels every learning phase', () => {
    expect(vocabularyPhaseLabel('scheduled_review')).toBe('到期复习')
    expect(vocabularyPhaseLabel('new')).toBe('今日新词')
    expect(vocabularyPhaseLabel('same_day_retry')).toBe('今日再复习')
    expect(vocabularyPhaseLabel('completed')).toBe('今日完成')
  })

  it('uses the correct continuation label for each next phase', () => {
    expect(vocabularyNextLabel('scheduled_review')).toBe('下一个复习词')
    expect(vocabularyNextLabel('new')).toBe('下一个新词')
    expect(vocabularyNextLabel('same_day_retry')).toBe('开始今日再复习')
    expect(vocabularyNextLabel('completed')).toBe('查看完成情况')
  })

  it('normalizes source punctuation before joining meanings', () => {
    expect(formatVocabularyMeanings(['first;', ' second\uFF1B ', 'third'])).toBe('first\uFF1Bsecond\uFF1Bthird')
  })

  it('identifies the legacy example placeholder', () => {
    expect(isVocabularyExamplePlaceholder('Remember how to use mention in a sentence.', 'mention')).toBe(true)
    expect(isVocabularyExamplePlaceholder('The teacher mentioned the new club.', 'mention')).toBe(false)
  })
})

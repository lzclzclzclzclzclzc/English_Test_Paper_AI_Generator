import type { VocabularyToday } from '@/types/api'

type VocabularyPhase = VocabularyToday['phase']

/** Remove source punctuation before the UI joins multiple senses. */
export function formatVocabularyMeanings(meanings: string[]): string {
  return meanings
    .map((meaning) => meaning.trim().replace(/[\uFF1B;\s]+$/u, '').trim())
    .filter(Boolean)
    .join('\uFF1B')
}

/** The original seed file contains this authoring placeholder, not an example. */
export function isVocabularyExamplePlaceholder(example: string, term: string): boolean {
  return example.trim().toLocaleLowerCase() === `remember how to use ${term.trim().toLocaleLowerCase()} in a sentence.`
}

const PHASE_LABELS: Record<VocabularyPhase, string> = {
  scheduled_review: '到期复习',
  new: '今日新词',
  same_day_retry: '今日再复习',
  completed: '今日完成',
}

export function vocabularyPhaseLabel(phase: VocabularyPhase): string {
  return PHASE_LABELS[phase]
}

export function vocabularyNextLabel(phase: VocabularyPhase): string {
  if (phase === 'same_day_retry') return '开始今日再复习'
  if (phase === 'completed') return '查看完成情况'
  if (phase === 'scheduled_review') return '下一个复习词'
  return '下一个新词'
}

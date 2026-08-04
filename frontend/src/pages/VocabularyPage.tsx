import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { getVocabularyToday, reviewVocabulary } from '@/api/vocabulary'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { queryClient } from '@/lib/queryClient'
import type { VocabularyRating } from '@/types/api'

const RATING_LABELS: Array<{ value: VocabularyRating; label: string; note: string }> = [
  { value: 'known', label: '认识', note: '进入下一次复习' },
  { value: 'fuzzy', label: '模糊', note: '明天再见一次' },
  { value: 'forgot', label: '不会', note: '回到第一档' },
]

export function VocabularyPage() {
  const [answer, setAnswer] = useState('')
  const [revealed, setRevealed] = useState(false)
  const [result, setResult] = useState<{ correct: string; spellingCorrect: boolean } | null>(null)
  const today = useQuery({ queryKey: ['vocabulary', 'today'], queryFn: getVocabularyToday })
  const card = today.data?.cards[0]
  const review = useMutation({
    mutationFn: (rating: VocabularyRating) => reviewVocabulary({ word_id: card!.word_id, answer, rating }),
    onSuccess: (data) => {
      setResult({ correct: data.correct_answer, spellingCorrect: data.spelling_correct })
      queryClient.invalidateQueries({ queryKey: ['vocabulary'] })
    },
  })

  const next = () => {
    setAnswer('')
    setRevealed(false)
    setResult(null)
  }

  if (today.isLoading) return <Skeleton className="h-72 w-full" />
  if (today.isError || !today.data) {
    return <div className="border-t border-hairline pt-8 text-sm text-muted-ink">今日单词任务加载失败，请稍后重试。</div>
  }

  return (
    <div className="mx-auto flex max-w-[42rem] flex-col gap-8">
      <PageHeader
        title="背单词"
        intro={`今天已完成 ${today.data.completed_count} 张，还剩 ${today.data.remaining_count} 张；复习词优先于新词。`}
      />

      {!card ? (
        <section className="border-t border-hairline pt-8">
          <h2 className="text-xl text-ink [font-family:var(--font-display)]">今日任务完成</h2>
          <p className="mt-3 text-sm leading-7 text-muted-ink">明天再来复习，记忆会更牢固。</p>
        </section>
      ) : (
        <section className="flex flex-col gap-7 border-t border-hairline pt-7">
          <div className="flex items-center justify-between text-xs tracking-wide text-quiet">
            <span>{card.card_type === 'review' ? '到期复习' : '今日新词'}</span>
            <span>{today.data.completed_count + 1} / {today.data.completed_count + today.data.remaining_count}</span>
          </div>
          <div>
            <p className="text-sm text-accent">{card.part_of_speech}</p>
            <p className="mt-2 text-2xl leading-relaxed text-ink">{card.meanings.join('；')}</p>
          </div>
          <blockquote className="border-l-2 border-accent/50 pl-4 text-[15px] leading-7 text-muted-ink">
            <p>{card.example_en}</p>
            <p className="mt-1 text-[13px] text-quiet">{card.example_zh}</p>
          </blockquote>

          {!result ? (
            <>
              <label className="flex flex-col gap-2 text-sm text-muted-ink">
                写出英文单词
                <input
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  onKeyDown={(event) => event.key === 'Enter' && setRevealed(true)}
                  className="h-11 rounded-sm border border-hairline bg-transparent px-3 text-base text-ink outline-none focus:border-accent"
                  placeholder="输入英文"
                  autoComplete="off"
                />
              </label>
              {!revealed ? (
                <Button className="self-start" disabled={!answer.trim()} onClick={() => setRevealed(true)}>查看答案</Button>
              ) : (
                <div className="flex flex-col gap-3 border-t border-hairline pt-5">
                  <p className="text-sm text-muted-ink">正确答案：<strong className="font-medium text-ink">{card.term}</strong></p>
                  <div className="flex flex-wrap gap-2">
                    {RATING_LABELS.map((item) => (
                      <Button
                        key={item.value}
                        variant={item.value === 'forgot' ? 'outline' : 'default'}
                        disabled={review.isPending}
                        onClick={() => review.mutate(item.value)}
                        title={item.note}
                      >
                        {item.label}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-start gap-4 border-t border-hairline pt-5">
              <p className="text-sm text-muted-ink">
                正确答案：<strong className="font-medium text-ink">{result.correct}</strong>
                <span className="ml-3">{result.spellingCorrect ? '拼写正确' : '拼写需要再练习'}</span>
              </p>
              <Button onClick={next}>下一张</Button>
            </div>
          )}
          {review.isError && <p className="text-sm text-accent">提交失败，请刷新后重试。</p>}
        </section>
      )}
    </div>
  )
}

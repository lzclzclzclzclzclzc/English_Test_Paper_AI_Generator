import { useState, useSyncExternalStore } from 'react'
import type { Passage } from '@/types/api'
import { cn } from '@/lib/utils'
import { speakStem, stopAll, subscribePlayingState, isGloballyPlaying } from '@/lib/tts'

interface PassageBlockProps {
  passage: Passage
  /** 'answering' 隐藏听力原文（仅靠听）；'review' 展示原文 */
  mode: 'answering' | 'review'
}

/**
 * 共享材料块：一段 passage 渲染一次，后跟同组小题。
 *
 * 听力材料（kind="listening"）：做题态仅显示播放控件（与 ListeningSingleChoiceField
 * 一致——学生靠听作答），交卷后 review 态才展示原文。阅读材料始终展示文本。
 *
 * TTS 复用 tts.ts 的 speakStem / stopAll / 全局播放锁，确保同一时间只播放一段。
 */
export function PassageBlock({ passage, mode }: PassageBlockProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const globallyPlaying = useSyncExternalStore(subscribePlayingState, isGloballyPlaying)

  const isListening = passage.kind === 'listening'
  const showContent = !isListening || mode === 'review'

  const handlePlay = async () => {
    if (isPlaying) {
      stopAll()
      setIsPlaying(false)
      return
    }
    setIsPlaying(true)
    try {
      await speakStem(passage.content)
    } finally {
      setIsPlaying(false)
    }
  }

  return (
    <div className="kk-rise mb-2 rounded-md border border-hairline p-5">
      {passage.title && (
        <p className="text-[11px] tracking-[0.1em] text-quiet">{passage.title}</p>
      )}

      {isListening && (
        <button
          onClick={handlePlay}
          disabled={!isPlaying && globallyPlaying}
          className={cn(
            'mt-2 flex w-fit items-center gap-2 rounded-sm border px-4 py-2 text-[14px] transition-colors',
            isPlaying || globallyPlaying
              ? 'cursor-not-allowed border-ink-15 text-quiet'
              : 'border-accent bg-wash text-accent hover:bg-accent hover:text-paper',
          )}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            {isPlaying ? (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            ) : (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
              />
            )}
          </svg>
          <span>{isPlaying ? '播放中...' : '播放听力'}</span>
        </button>
      )}

      {showContent && (
        <div className="mt-3 flex flex-col gap-1 text-[15px] leading-[1.9]">
          {passage.content.split('\n').map((line, index) => {
            const speakerMatch = line.match(/^(M|W):\s*(.*)$/)
            if (speakerMatch) {
              const [, speaker, text] = speakerMatch
              return (
                <p key={index} className="text-muted-ink">
                  <span className="mr-2 font-mono text-[13px] text-quiet">
                    {speaker === 'M' ? '♂ M' : '♀ W'}
                  </span>
                  <span>{text}</span>
                </p>
              )
            }
            return (
              <p key={index} className="text-ink">
                {line}
              </p>
            )
          })}
        </div>
      )}
    </div>
  )
}

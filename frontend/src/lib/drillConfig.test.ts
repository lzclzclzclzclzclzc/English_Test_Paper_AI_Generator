import { describe, expect, it } from 'vitest'
import { MAX_QUESTIONS, questionsPerUnit, unitOf } from '@/lib/composeQuery'
import {
  DRILL_CONFIGS,
  DRILL_FAMILIES,
  HIDDEN_KP_IDS,
  THIN_KP_IDS,
  drillBySlug,
} from '@/lib/drillConfig'
import { TYPE_FAMILY, TYPE_LABELS } from '@/lib/kp'

describe('DRILL_CONFIGS 完备性', () => {
  it('题型与 TYPE_LABELS 一一对应,不缺不重', () => {
    expect(DRILL_CONFIGS.map((c) => c.type).sort()).toEqual(
      Object.keys(TYPE_LABELS).sort(),
    )
  })
  it('slug 唯一', () => {
    const slugs = DRILL_CONFIGS.map((c) => c.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
  })
  it('族与 TYPE_FAMILY 一致,label 与 TYPE_LABELS 一致', () => {
    for (const c of DRILL_CONFIGS) {
      expect(c.family).toBe(TYPE_FAMILY[c.type])
      expect(c.label).toBe(TYPE_LABELS[c.type])
    }
  })
  it('单位与 composeQuery.unitOf 一致', () => {
    for (const c of DRILL_CONFIGS) expect(c.unit).toBe(unitOf(c.type))
  })
  it('档位均为正整数且不超过 maxCount', () => {
    for (const c of DRILL_CONFIGS) {
      for (const n of c.countPresets) {
        expect(Number.isInteger(n) && n >= 1).toBe(true)
        expect(n).toBeLessThanOrEqual(c.maxCount)
      }
    }
  })
  it('maxCount 折算题数不破单卷上限', () => {
    for (const c of DRILL_CONFIGS) {
      expect(c.maxCount * questionsPerUnit(c.type)).toBeLessThanOrEqual(MAX_QUESTIONS)
    }
  })
  it('KP/主题仅语法族开放（作文自成一族，无 KP 细分）', () => {
    for (const c of DRILL_CONFIGS) {
      const kpEligible = c.family === 'grammar'
      expect(c.supportsKp).toBe(kpEligible)
      expect(c.supportsTopic).toBe(kpEligible)
    }
  })
  it('阅读首字母与作文锁定 original,其余三档可选', () => {
    for (const c of DRILL_CONFIGS) {
      if (c.type === 'reading_first_blank' || c.type === 'writing') {
        expect(c.intensity).toEqual({ locked: 'original' })
      } else {
        expect(c.intensity).toEqual({
          options: ['original', 'light', 'fresh'],
        })
      }
    }
  })
})

describe('drillBySlug / DRILL_FAMILIES', () => {
  it('按 slug 查得且未知 slug 返回 undefined', () => {
    expect(drillBySlug('cloze')?.type).toBe('cloze_single_choice')
    expect(drillBySlug('nope')).toBeUndefined()
  })
  it('四族分区顺序语法→听力→阅读→写作,数量语法 3、听力 3、阅读 3、写作 1', () => {
    expect(DRILL_FAMILIES.map((f) => f.family)).toEqual(['grammar', 'listening', 'reading', 'writing'])
    const byFamily = Object.fromEntries(DRILL_FAMILIES.map((f) => [f.family, f.configs.length]))
    expect(byFamily).toEqual({ grammar: 3, listening: 3, reading: 3, writing: 1 })
  })
})

describe('薄尾 KP 清单', () => {
  it('隐藏集是薄尾集的子集', () => {
    for (const id of HIDDEN_KP_IDS) expect(THIN_KP_IDS.has(id)).toBe(true)
  })
  it('零题量的宾语从句被隐藏', () => {
    expect(HIDDEN_KP_IDS.has('kp_sc_object_clause')).toBe(true)
  })
})

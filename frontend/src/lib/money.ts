/** 分 → 人民币展示,去掉多余的尾零:990 → ¥9.9,2500 → ¥25。 */
export function formatYuan(cents: number): string {
  return `¥${(cents / 100).toFixed(2).replace(/\.?0+$/, '')}`
}

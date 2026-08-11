const LOOP_ITEMS = [
  { title: '弱点画像', desc: '每道题都记入 55 个知识点的掌握度，薄弱点一目了然。' },
  { title: '错题本与重练', desc: '错过的题自动进错题本，一键出一份巩固卷。' },
  { title: '弱点复习卷', desc: '根据答题记录算出该补什么，出一份查漏补缺的卷子。' },
] as const

/** #loop 学习闭环:左「判分与讲解」+ 模拟讲解框,右「错题沉淀」三行列表。 */
export function LoopSection() {
  return (
    <section
      id="loop"
      className="grid scroll-mt-20 grid-cols-2 gap-[72px] border-t border-hairline py-14 max-md:grid-cols-1 max-md:gap-12"
    >
      <div>
        <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">
          交卷那一刻，才是开始
        </h2>
        <p className="mt-4 max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
          客观题即交即判，错哪道当场知道。讲解不是标准答案的复读——AI
          看得到你写的那个错误答案，讲的是你为什么会错、下次怎么想。
        </p>
        {/* 模拟讲解框:错题行(赤陶)+ 讲解摘录 */}
        <div className="mt-6 rounded-md border border-hairline p-5">
          <p className="font-ui text-[13px] text-accent">✕ 你选了 B (has gone)</p>
          <p className="mt-3 border-t border-hairline pt-3 text-[14px] leading-[1.9] text-muted-ink">
            has gone 表示“去了还没回”，而句中 Tom 现在就在上海，应该用 has been in +
            时间段来表达一直住到现在……
          </p>
        </div>
      </div>
      <div>
        <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">
          错题不白错
        </h2>
        <div className="mt-4">
          {LOOP_ITEMS.map((item) => (
            <div key={item.title} className="border-t border-hairline py-[18px] last:border-b">
              <div className="text-[17px] text-ink">{item.title}</div>
              <p className="mt-2 text-[14px] leading-[1.8] text-muted-ink">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

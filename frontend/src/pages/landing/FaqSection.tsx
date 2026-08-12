const FAQS = [
  {
    q: '题目是哪里来的？',
    a: '来自上海中考一模、二模真题书及听力/阅读/作文素材，经章节切分、知识点归并、人工审核入库，每道题都保留题源与考点标注，共 1,428 道。',
  },
  {
    q: '练多了会不会重复？',
    a: '选『AI 改编』或『全新原创』时引擎会换词、换语境甚至从零命题，同一考点每次都是新题；选『真题原样』则忠实还原，题目右上角永远标明出身。',
  },
  {
    q: '听力题怎么播放？',
    a: '由 AI 语音朗读，浏览器里直接点击播放，可反复听，不需要下载任何文件。',
  },
  {
    q: '免费能用到什么程度？',
    a: '注册即可每天免费生成 3 份卷子、看 2 次 AI 讲解；做题、判分、错题本、掌握度记录全部免费且不限量。',
  },
  {
    q: '会员怎么收费，会自动扣费吗？',
    a: '月度 9.9 元、季度 25 元、年度 88 元，支付宝付款，到期不自动续费；续费时长从当前有效期顺延。',
  },
] as const

/** #faq 常见问题:细线行列表,全展开无手风琴。 */
export function FaqSection() {
  return (
    <section id="faq" className="scroll-mt-20 border-t border-hairline py-14">
      <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">
        常见问题
      </h2>
      <div className="mt-6 max-w-[42rem]">
        {FAQS.map((f) => (
          <div key={f.q} className="border-t border-hairline py-6 first:border-t-0 first:pt-2">
            <h3 className="text-[17px] text-ink">{f.q}</h3>
            <p className="mt-2.5 text-[15px] leading-[1.9] text-muted-ink">{f.a}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

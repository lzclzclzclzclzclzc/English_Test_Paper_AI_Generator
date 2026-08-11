/** #assistant 学习助手:左文案(含背单词一句),右静态两轮对话摘录。 */
export function AssistantSection() {
  return (
    <section
      id="assistant"
      className="grid scroll-mt-20 grid-cols-2 gap-[72px] border-t border-hairline py-14 max-md:grid-cols-1 max-md:gap-12"
    >
      <div>
        <h2 className="text-[24px] font-normal text-ink [font-family:var(--font-display)]">
          一个会安排学习的 AI 教练
        </h2>
        <p className="mt-4 max-w-[42rem] text-[15px] leading-[1.9] text-muted-ink">
          不想自己琢磨练什么，直接和学习助手聊。它主要替你做两件事：
        </p>
        <ul className="mt-4 flex max-w-[42rem] flex-col gap-3">
          <li className="text-[15px] leading-[1.8] text-muted-ink">
            <span className="text-ink">一句话出卷</span> — 说出想练的题型、考点、题量，它当场从真题库出一份能直接做的卷子，同样每题标注真题出处。
          </li>
          <li className="text-[15px] leading-[1.8] text-muted-ink">
            <span className="text-ink">排学习计划</span> — 按你的考试日期和薄弱环节，排出一份多天计划，每天该练什么、练多少一条条想好，点一下就能逐日出卷开练。
          </li>
        </ul>
        <p className="mt-4 max-w-[42rem] text-[14px] leading-[1.9] text-quiet">
          也能随时找它讲题、查某个考点的例题。
        </p>
        <p className="mt-6 border-t border-hairline pt-4 text-[14px] leading-[1.9] text-muted-ink">
          还有<span className="text-ink">背单词</span>
          — 国家核心 1600 词，按间隔重复安排复习节奏，每天一组今日卡片。
        </p>
      </div>
      {/* 静态对话摘录:用户 = wash 底右对齐,助手 = 无框正文 + 底部细线(同学习助手页) */}
      <div className="flex flex-col gap-5">
        <p className="ml-auto max-w-[85%] rounded-md bg-wash px-4 py-2.5 text-[14.5px] leading-[1.8] text-ink">
          我下周三要考试，听力比较差，帮我安排一下
        </p>
        <p className="border-b border-hairline pb-5 text-[14.5px] leading-[1.9] text-muted-ink">
          好的。距离考试还有 6 天：前 4 天每天 1 份听力专项（选择 + 填词各半），第 5
          天做一份弱点复习卷，考前一天只复盘错题本。现在先出今天的第一份吗？
        </p>
      </div>
    </section>
  )
}

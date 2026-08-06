/** #assistant 学习助手:左文案(含词汇学习「即将上线」badge),右静态两轮对话摘录。 */
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
          不想自己琢磨练什么，就直接和学习助手聊：它能替你出卷、讲题，也能按你的目标排出一份多天学习计划，每天该练什么、练多少，一条条替你想好。
        </p>
        <p className="mt-6 border-t border-hairline pt-4 text-[14px] leading-[1.9] text-muted-ink">
          词汇学习
          <span className="mx-2 rounded-sm border border-hairline px-1.5 py-0.5 font-ui text-[11px] text-quiet">
            即将上线
          </span>
          — 国家核心 1600 词，按间隔重复安排复习节奏。
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

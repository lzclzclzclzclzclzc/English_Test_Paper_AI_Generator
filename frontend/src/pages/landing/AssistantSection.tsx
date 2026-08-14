const FEATURES = [
  { i: '01', title: '一句话出卷', desc: '说出想练的题型、考点、题量，它当场从真题库出一份能直接做的卷子，同样每题标注真题出处。' },
  { i: '02', title: '排学习计划', desc: '按你的考试日期和薄弱环节，排出一份多天计划，每天该练什么、练多少一条条想好，点一下就能逐日出卷开练。' },
  { i: '＋', title: '讲题与查考点', desc: '也能随时找它讲题、查某个考点的例题。' },
  { i: '＋', title: '背单词', desc: '国家核心 1600 词，按间隔重复安排复习节奏，每天一组今日卡片。' },
] as const

/** #assistant 学习助手:硬边两栏——左能力清单(feat-list)+ 右静态对话摘录(chat)。 */
export function AssistantSection() {
  return (
    <section className="section" aria-label="学习助手">
      <div className="l-wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow-row"><span className="idx">ASSISTANT</span><hr className="hairline" /></div>
            <h2 className="h-sec">一个会安排<br />学习的 AI 教练</h2>
          </div>
          <p className="lead">不想自己琢磨练什么，直接和学习助手聊——出卷、排计划、讲题、背单词，一个入口全包。</p>
        </div>

        <div className="two-col">
          <div className="col">
            <h3>一个会安排学习的 AI 教练</h3>
            <p>不想自己琢磨练什么，直接和学习助手聊。它主要替你做两件事：</p>
            <ul className="feat-list">
              {FEATURES.map((f, i) => (
                <li key={i}>
                  <div className="ft"><span className="i">{f.i}</span> {f.title}</div>
                  <p>{f.desc}</p>
                </li>
              ))}
            </ul>
          </div>
          <div className="col">
            <div className="chat">
              <div className="bubble user">
                <div className="who">User · 用户</div>
                <p>我下周三要考试，听力比较差，帮我安排一下</p>
              </div>
              <div className="bubble bot">
                <div className="who">Assistant · 助手</div>
                <p>好的。距离考试还有 6 天：前 4 天每天 1 份听力专项（选择 + 填词各半），第 5 天做一份弱点复习卷，考前一天只复盘错题本。现在先出今天的第一份吗？</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

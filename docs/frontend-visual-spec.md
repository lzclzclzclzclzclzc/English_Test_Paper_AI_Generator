# 前端视觉规范 —「喫茶去」

> Spec F v2 · 2026-07-27 改版。视觉来源：设计交接包 `design_handoff_test_paper_ui`
> （`English Test Paper AI Generator.zip`，内含 hifi 原型 `试卷生成器.dc.html` + `tokens/*.css`）。
> 取代 2026-07-07 的「墨卷」版（v1，藏青墨蓝 + 卷面拟物）；卷面语言（装订线、文武线、分数章）随 v1 一并废弃。
> 配合 Spec D（frontend-design）使用：Spec D 定功能结构，本文定视觉表现。

---

## 1. 设计理念

**暖纸底 · 软炭墨字 · 单一赤陶强调。** 整个界面像一页安静的书：全站衬线字、
1px 细线分层、大量留白；唯一的饱和色（赤陶 Terracotta Coral）只出现在
可交互与需要强调的地方。没有卡片、没有阴影、没有拟物装饰。

### 三条硬规则（实现必须守住）

1. **One Chroma Rule** — 赤陶是全站唯一的饱和色，只用于交互与强调
   （主按钮、选中态、当前导航项、进度条、错题标记、薄弱知识点）。
   **不用绿/黄/红做语义色**：对错用「✓ 墨色边 / ✕ 赤陶」表达，
   掌握度用赤陶不透明度分级表达（见 § 6 掌握度）。
2. **Tinted Neutral Rule** — 禁止 `#000` / `#fff` 和无色阶灰。所有边框、
   分隔线、hover 底色都是不透明度分级的墨色（`--ink-5/10/15/20/30`）。
   唯一例外：支付二维码底必须纯白（扫码识别的功能性要求）。
3. **Flat-Paper Rule** — 无静置阴影、无卡片盒子、无左边框强调条。
   层次靠 1px 细线、色调底纹（`--hover-tint` / `--accent-wash`）和留白。
   阴影只允许出现在真正悬浮的覆盖层（Dialog / Select 下拉）。

---

## 2. 设计 Tokens

**来源即真相**：交接包 `tokens/colors.css / typography.css / spacing.css / base.css`
原样拷入 `frontend/src/styles/`，由 `index.css` 引入。改 token 值请改这些文件，
不要在组件里写死颜色。核心值：

| Token | 值 | 用途 |
|---|---|---|
| `--ink` | `oklch(38% 0.004 90)` ≈ `#353534` | 所有文字、边框的基色 |
| `--rice-cream` / `--surface-page` | `oklch(96.8% 0.005 95)` ≈ `#f6f5f1` | 页面底色 |
| `--accent` | `oklch(49% 0.155 33)` 赤陶 | 唯一强调色 |
| `--accent-wash` | `color-mix(accent 18%, transparent)` | 主按钮底、选中底、`<mark>` 高亮底 |
| `--ink-5 / 10 / 15 / 20 / 30` | 墨色 5%–30% | hover 底 / 弱线 / 默认细线 / 强线（输入框边） / 下划线 |
| `--border-hairline` | `= --ink-15` | 默认 1px 分隔线 |
| `--text-muted` / `--text-quiet` | 墨色 82% / 75% | 次要文字 / 标签与日期（对比度下限） |
| 深色模式 | `.dark` 类 | 底 `oklch(24% 0.016 72)` 暖炭，字暖白，强调 `oklch(72% 0.13 35)` 亮赤陶 |

### Tailwind 语义类映射（`index.css` @theme）

| 类 | 指向 |
|---|---|
| `text-ink` / `text-muted-ink` / `text-quiet` | `--ink` / `--text-muted` / `--text-quiet` |
| `text-accent` `border-accent` | `--accent` |
| `bg-wash` | `--accent-wash` |
| `bg-tint` | `--hover-tint`（hover 薄底） |
| `border-hairline` | `--border-hairline` |
| `border-ink-10/15/20/30`、`divide-ink-10` | 对应墨色阶 |

shadcn 变量（`--background/--foreground/--border/--primary/--ring/--muted-foreground` 等）
全部指向上述 token，shadcn 组件自动进入这套外观。
Button 变体已重写：default = 赤陶边 + wash 底 + 墨字（hover 字转赤陶）；
outline/secondary = 细线边透明底（hover 转赤陶边字 + tint 底）。

---

## 3. 字体与字重

- 全站衬线：正文 `--font-serif`（拉丁 Georgia、中文 Noto Serif SC，
  Google Fonts 只载 400/700 两个字重，见 `index.html`）。
- 品牌（侧栏 / 落地页页眉 / 登录页左栏）用 `--font-display`（京华老宋体）。
  子集 woff2 未随交接包提供，当前回退到正文衬线（handoff 允许，补上字体文件即生效）。
- 代码 / 题号 / 日期 / wilson 分数用 `--font-mono`（系统等宽）。
- **只有 400 和 700 两个字重**。`index.css` 已把 Tailwind 的
  `font-medium → 400`、`font-semibold → 700`，不会出现中间字重。

**字号 / 行高**（px）：落地页大标题 58/1.32；页面 h1 30/400；区块 h2 24/400；
小节标题 17–19；正文 15–16，行高 1.9，正文宽度上限 42rem；表格与元信息 13–14；
标签 10.5–12 / 700 / letter-spacing 0.1–0.14em（拉丁大写标签）。

**圆角**：`0.25rem`（按钮、chip、格子）、`0.375rem`（代码块、解析框、头像）、
`3px`（输入框）。**不要用胶囊圆角**（`rounded-full` 只保留在 review 状态圆点等
功能性圆形上）。

**间距**：内容区左右 56px（`AppLayout` 的 `px-14`）；屏内区块间 40–56px；
列表项上下 18–28px；网格 gap 8–20px。

**动效**：只有两个，定义在 `index.css` ——
`kk-rise`（opacity 0→1 + translateY 8px→0，0.3s ease-out，面板展开）、
`kk-pulse`（opacity 0.35↔1，1.1s，管线当前步骤圆点）。宽度过渡 0.25–0.4s
ease-out。无弹跳、无装饰性循环；`prefers-reduced-motion` 时全部关闭（base.css）。

---

## 4. 应用外壳：左侧可折叠导航（`Sidebar.tsx`）

- 展开 232px / 收起 66px，`transition: width .25s ease-out`，粘顶全高，右侧 1px 细线。
- 顶部 64px：品牌「试卷生成器」（display 字体，收起时隐藏）+ 30×30 折叠按钮（lucide `panel-left`）。
- 三组导航，组标签 10.5px/700/0.14em 弱色：
  **出卷**（生成试卷 `/`、历史试卷 `/papers`）、
  **复习**（错题本 `/review`、掌握度 `/mastery`）、
  **资料**（会员 `/membership`、设置 `/settings`）。
  收起时组标签变成一条 1px 细线分隔符。
- 导航项：lucide 图标 18px（strokeWidth 1.5）+ 14.5px 文字，padding 9/12，圆角
  0.25rem。当前项 = `--accent-wash` 底 + 赤陶字；非当前 = 透明底 + `--text-muted`。
- 底部：30×30 头像方块（tint 底）+ 用户名（+ 会员小标）+「登出」小字链接。
- 折叠状态持久化 `localStorage['sidebarCollapsed']`。

每个应用内页面顶部保留一个 11px 大写弱色**端点小标签**（如
`POST /API/PAPERS/GENERATE`），标注「这屏对应哪个接口」；上线可整体去掉。

---

## 5. 屏幕清单与实现状态

| # | 屏幕 | 路由 | 状态 |
|---|------|------|------|
| 1 | 落地页（未登录） | `/welcome` | ✅ `LandingPage`：粘顶磨砂页眉 + hero（58px 标题、`<mark>` 高亮、唯一 CTA）+ 4 项赤陶数据条 + `#how` 四列流程 + `#engine` 模式/判分 + `#bank` 题库工序 chips |
| 2 | 登录 / 注册 | `/login` | ✅ 左右两栏（1.15fr/1fr 竖细线）；左栏品牌/26px 说明句/底部小字，右栏 24rem 表单，tab 选中 2px 赤陶下边框 |
| 3 | 应用外壳 | — | ✅ 见 § 4 |
| 4 | 生成试卷 | `/` | ✅ 44rem textarea + 建议 chips + 主按钮 + 状态小字 + `PipelineProgress` 管线面板（见下） |
| 5 | 当前试卷 / 作答 | `/papers/:id` | ✅ 两栏 `minmax(0,1fr) 280px`：左 52rem 长卷（PAPER·id 标签、题目 `<article>` 细线分隔、纵向选项列表、下划线填空），右粘顶答题卡（N/12 + 2px 进度条 + 4 列题号格） |
| 6 | 成绩与解析 | 同上（交卷后） | ✅ 总分 44px / 答对 / 错题（赤陶）统计行 + ✓/✕ 状态圆 + 解析手风琴（kicker `POST /API/SOLUTIONS · 按需生成`） |
| 7 | 掌握度 | `/mastery` | ✅ 统计行 + 考点行网格 `minmax(0,1fr) 88px 200px 64px`，6px 赤陶进度条按不透明度分级，底部薄弱点总结 + 出卷入口 |
| 8 | 历史试卷 | `/papers` | ✅ 无卡片行式列表 `110px minmax(0,1fr) auto`，整行可点 hover tint |
| 9 | 错题本 | `/review` | ✅ 勾选方块（选中 = 赤陶边 + wash + ✓）+ 行式列表 + 两个出卷入口（REMEDIATION / REVIEW 分栏），底部计数 `已选 N 道 · mode=remediation` |
| 10 | 题库浏览 | — | ⏸ 未做：需后端只读检索端点（`GET /api/questions?…`），见 Spec D § 11 |
| 11 | 题库摄入控制台 | — | ⏸ 未做：管理员向功能，需 ingestion 状态端点，分阶段上线（handoff 允许） |
| 12 | 设置 | `/settings` | ✅ 细线行式列表：账号 / 阅读外观（纸色 Ink · 深墨地 Deep Ink 切换 `.dark`，持久化 `localStorage['theme']`）/ 速率限制说明 |
| — | 会员（本仓库特有，不在 handoff 内） | `/membership` | ✅ 按同一语言重做：细线分栏套餐、赤陶价格、细线表格权益对比 |

**管线进度（第 4 屏）**：后端同步返回、无 SSE（Spec C 明确），采用 handoff
落地方式 (a)——固定时间轴演示四步（Parser 0.8s / Retriever 1.2s / Reviser 2.6s /
Assemble 0.3s，文案照抄 handoff），右上角 0.1s 精度真实计时；请求完成即导航离开。
若后端未来加 SSE，把 `PipelineProgress` 的时间轴换成真实事件即可。

---

## 6. 组件规则速查

| 元素 | 规则 |
|---|---|
| 主按钮 | 1px 赤陶边 + `--accent-wash` 底 + 墨字，hover 字转赤陶；无填充色按钮 |
| 次按钮 | 1px 细线边 + 透明底 + `--text-muted` 字，hover 赤陶边字 + tint 底 |
| 分段按钮/chip 选中 | 赤陶边 + wash 底（统计窗口、主题切换、勾选方块、单选选项同语言） |
| 输入框 | 3px 圆角、1px `--ink-20` 边，focus 边框转赤陶；填空题只有 1px 底线 |
| 对错 | 对 = ✓ 墨色边圆圈；错 = ✕ 赤陶。**无绿色** |
| 掌握度条 | 6px 高赤陶条：wilson < 0.4 全饱和（薄弱更醒目），≥ 0.4 opacity 0.45；分数等宽字，薄弱赤陶 |
| 解析框/代码框 | 0.375rem 圆角 + 1px 细线，无底色或同纸底 |
| hover | 统一 `--hover-tint` 薄底或文字转赤陶。**无位移、无阴影、无放大** |
| 列表 | 一律细线分隔的行，不用卡片容器；表头 11px 大写弱色 + `--ink-20` 下边线 |
| 空态 | 细线上起段：标题 + 一句引导 + 主按钮指向唯一下一步 |

---

## 7. 状态管理补充（相对 Spec D）

- 新增 UI 状态：`sidebarCollapsed`（localStorage）、`theme`（localStorage，
  `main.tsx` 渲染前应用避免闪屏）、`reviseOpen`（试卷页内联面板，替代 Dialog）。
- 答题卡组件（`AnswerCard`）与试卷正文读同一份 `answers`，不复制第二份；
  `answers` 只在内存，刷新丢失（Spec D § 4.3 已接受）。

## 8. 与设计交接包的差异清单

1. **生成页无「出卷模式 / 题量 / 知识点 chips」分段控件**：本仓库产品结构是
   fresh 在生成页、remediation/review 在错题本页（配合会员门槛与本地错题本），
   题量/考点由 AI 从自然语言解析。属有意保留的产品差异。
2. **落地页路由为 `/welcome`**（handoff 为未登录的 `/`）：`/` 保留给应用内
   生成页，未登录访问受保护路由仍跳 `/login`（登录页与落地页互链）。
3. **历史试卷右侧状态**只有「已交卷 / 未作答」，无「已交 45/60」分数——
   `GET /api/papers` 摘要无得分字段（后端缺口，见 Spec D § 11）。
4. **题库浏览、摄入控制台**未做（端点缺失，见 § 5 表格）。
5. **京华老宋体**字体文件未随包提供，display 字体暂回退正文衬线。
6. 会员/支付界面是本仓库特有功能，按喫茶去语言自行延展设计。

## 9. 禁用清单

- 纯白 `#fff` / 纯黑 `#000`（页面永远 `--surface-page`；例外仅支付二维码底）
- 绿/黄/红语义色；渐变、emoji、左边框强调条、卡片盒子、静置阴影
- 胶囊圆角；400/700 之外的字重；非 `kk-rise`/`kk-pulse` 的装饰动效
- 小于 10.5px 的文字（10.5–12px 仅限大写字距标签，正文不低于 13px）

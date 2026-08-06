# 前端设计（Spec D）

> 面向对象：中考英语试卷生成器（产品名 **墨卷**）的 Web 前端。
> 依赖：[Spec A（题库摄入）](./2026-07-07-question-bank-ingestion-design.md)、[Spec B（AI Engine）](./2026-07-07-ai-engine-design.md)、[Spec C（后端）](./2026-07-07-backend-design.md)。
> 后置：[Spec E（跨系统测试）](./2026-07-07-testing-design.md)（待写）。
> 2026-07-27 改版：视觉与信息架构按设计交接包「喫茶去」重构（左侧可折叠导航 +
> 多屏结构 + 落地页/设置页），视觉规则全部移至 [Spec F v2（frontend-visual-spec）](./frontend-visual-spec.md)；
> 本文中与其冲突的旧描述以带删除线的修订标注为准。

---

## 0. 范围与依赖

### 0.1 本 Spec 负责
- 浏览器端应用（用户交互层）。
- 八个页面：**登录页 / 学习助手（AI 对话首页）/ 错题复习 / 学习计划 / 我的试卷 / 试卷详情 / 掌握度 / 会员**。
- 与后端（Spec C）之间的 HTTP 调用契约的**消费方**约定（不定义契约，契约在 Spec C），以及与独立支付小服务（`payment/`，`:8001`）的调用。
- 前端组件测试策略。

### 0.2 本 Spec 不负责
- HTTP 契约、错误码：见 Spec C § 6~§ 8。
- 数据契约类型（`Paper`、`RevisedQuestion` 等）：见 Spec A § 2 与 Spec C § 4。前端**通过 TypeScript 手写等价类型**保持同步（见 § 4.3）。
- 端到端测试：见 Spec E。

### 0.3 与前面 Spec 的关系
本 Spec 只消费 Spec C 已经确定的 HTTP 契约，不覆盖任何 Spec C 决策。

---

## 1. 架构总览

### 1.1 部署形态（复述 Spec C § 1.1）
**部署形态 C**：
- **开发时**：Vite dev server（`localhost:5173`） + FastAPI（`localhost:8000`），Vite 配置 `/api` 代理到 8000、`/payapi` 代理到支付小服务 8001，避开 CORS。
- **部署时**：`vite build` 产出 `dist/`；FastAPI 用 `StaticFiles` 挂载 `dist/`，前后端同源，同一进程。

### 1.2 依赖方向
```
前端 (Spec D) ──HTTP──> 后端 (Spec C) ──函数调用──> AI Engine (Spec B)
                                              └──> 题库/掌握度 (Spec A)
```
前端**不直接触碰** AI Engine 或 SQLite/Chroma。

### 1.3 状态所有权
- **服务端状态**（试卷、掌握度、用户身份）：由后端持有，前端通过 TanStack Query 缓存 + 失效。
- **UI 状态**（当前正在做的题目答案、题目展开/折叠）：前端 React state。
- **提交前的答题状态**：仅存在于内存中；如果用户刷新页面，前端从 `GET /api/papers/{id}` 重新拉试卷，但**已填的答案会丢失**（MVP 不做草稿保存）。

---

## 2. 技术栈与目录结构

### 2.1 技术栈
| 用途 | 选型 |
|------|------|
| 构建 | Vite（React + TypeScript 模板） |
| UI 库 | shadcn/ui（基于 Radix + Tailwind） |
| 路由 | React Router v6 |
| 服务端状态 | TanStack Query v5 |
| HTTP 客户端 | 原生 `fetch`（薄封装，见 § 5） |
| 表单 | React Hook Form + Zod |
| Markdown 渲染 | react-markdown + remark-gfm（学习助手对话，支持 GFM 表格） |
| Toast | sonner |
| 组件测试 | Vitest + @testing-library/react |
| 代码质量 | ESLint + Prettier + TypeScript strict |

### 2.2 目录结构
```
frontend/
  index.html
  vite.config.ts
  tsconfig.json
  package.json
  src/
    main.tsx                 # React 入口，挂载 <App/>
    App.tsx                  # Providers（QueryClient、Router）
    routes.tsx               # 路由表 + Guard（AppRoutes）
    types/
      api.ts                 # 与 Spec C 对齐的 TS 类型（手写）
      payment.ts             # 支付小服务的类型
    api/
      client.ts              # fetch 封装（apiFetch → /api，payFetch → /payapi）+ 错误映射
      auth.ts                # login/register/logout/me
      papers.ts              # generate/revise/get/list
      solutions.ts           # 解析获取
      attempts.ts            # 提交答题 + 按试卷取历史结果
      mastery.ts             # 掌握度
      agent.ts               # 学习助手对话 + 学习计划
      knowledgePoints.ts     # 知识点目录（id→中文名）
      payment.ts             # 会员 / 套餐 / 下单（走 /payapi）
      health.ts              # 题库就绪探针
    pages/
      LoginPage.tsx          # 登录 / 注册
      GeneratePage.tsx       # 学习助手：AI 多轮对话首页（/）
      ReviewPage.tsx         # 错题复习：错题巩固 / 综合复习入口 + 本地错题本
      StudyPlanPage.tsx      # 学习计划：按天打卡
      PapersPage.tsx         # 我的试卷列表
      PaperPage.tsx          # 试卷详情：做题 / 复盘（PaperPageRoute）
      MasteryPage.tsx        # 掌握度报告
      MembershipPage.tsx     # 会员 / 支付
    components/
      ui/                    # shadcn/ui 生成的组件
      AppLayout.tsx          # 受保护页共享布局（导航 + 内容区 + 知识点目录预取）
      AppNav.tsx             # 顶部导航（6 个入口 + 会员标 + 头像 + 退出）
      RequireAuth.tsx        # 路由守卫
      PaperSheet.tsx         # 卷面外壳
      QuestionCard.tsx       # 单题渲染（单选/词形/改写；答题/复盘两态）
      GradeBanner.tsx        # 成绩条 + 分数章（ScoreStamp）
      SolutionBlock.tsx      # 单题解析（带 user_answer 的定向解析）
      RequestSummary.tsx     # 生成请求回显
      MasteryReport.tsx      # 掌握度报告主体
      UpgradeDialog.tsx      # 会员升级弹窗 + MemberPill
      PayQrDialog.tsx        # 支付扫码 / 收银台弹窗
      GenerateForm.tsx       # 结构化出卷表单（错题复习页内复用）
      review/                # 错题复习页子组件
      question-fields/       # 各题型输入控件
    hooks/
      useAuth.ts             # 当前用户
      usePaper.ts            # 单份试卷缓存
      useGeneratePaper.ts    # 出卷共享逻辑（会员门槛 + 配额 + 导航）
      useMembership.ts       # 会员状态（locked / isMember / expiresAt）
      useKnowledgePoints.ts  # 知识点目录预取 + 注册 id→中文名
    lib/
      queryClient.ts
      errors.ts              # ErrorResponse → 用户可读文本 / toast
      answers.ts             # 答题草稿 → 提交体
      paperNotices.ts        # metadata → 中文说明条
      wrongBook.ts           # 本地错题本
      quota.ts               # 非会员每日免费配额
      kp.ts                  # prettifyKp：KP id → 中文名
      money.ts               # 金额格式化
```

### 2.3 TypeScript 配置要点
- `strict: true`，`noUncheckedIndexedAccess: true`。
- `paths` 别名：`@/` → `src/`。
- 依赖版本在 `package.json` 中固定次版本（`^` 而非 `*`）。

---

## 3. 页面与路由

### 3.1 路由表（2026-07-27 随喫茶去改版更新）
| 路径 | 页面 | 是否需登录 | 说明 |
|------|------|-----------|------|
| `/welcome` | LandingPage | 否 | 对外落地页（产品介绍，CTA 指向 `/login`） |
| `/login` | LoginPage | 否 | 登录 + 注册（切换 tab），左右两栏布局 |
| `/` | GeneratePage | 是 | 生成试卷（fresh 模式表单 + 管线进度演示） |
| `/assistant` | AssistantPage | 是 | 学习助手：与 study-coach agent 多轮对话（可出卷 / 查例题 / 制定计划） |
| `/papers` | PapersPage | 是 | 历史试卷列表 |
| `/papers/:paperId` | PaperPage | 是 | 试卷详情：做题 / 交卷判分 / 复盘回放（同屏切换） |
| `/review` | ReviewPage | 是 | 错题本 + 错题巩固 / 综合复习出卷入口 |
| `/mastery` | MasteryPage | 是 | 用户掌握度报告 |
| `/study-plan` | StudyPlanPage | 是 | 学习计划：按天打卡 |
| `/membership` | MembershipPage | 是 | 会员开通 / 续费（支付子系统） |
| `/settings` | SettingsPage | 是 | 账号信息 · 阅读外观（深色切换）· 速率限制说明 |
| `*` | 重定向到 `/` | — | 未匹配的 URL |

需登录的页面统一挂在 `<RequireAuth><AppLayout/></RequireAuth>` 之下：`AppLayout` 渲染
左侧可折叠导航 `Sidebar`（232/66px，三组：出卷 = 生成试卷 / 学习助手 / 历史试卷，
复习 = 错题本 / 掌握度 / 学习计划，资料 = 会员 / 设置；见 Spec F v2 § 4）+ `<Outlet/>`，
并在挂载时预取知识点目录（见 § 3.9）。侧栏底部是用户名首字母头像、会员标与「登出」。

> 合并说明（2026-07-29）：dev 曾把学习助手放在 `/` 取代出卷表单；并入喫茶去改版后
> 二者共存——`/` 保留 handoff 的结构化出卷表单，对话式入口独立成 `/assistant`。

### 3.2 路由守卫
- 使用 `<RequireAuth>` 高阶组件包裹需要登录的路由：
  - 挂载时读 `useAuth()`（内部是 `useQuery(['auth','me'])`）。
  - 已有用户对象 → 渲染 children。
  - 无用户对象（`useQuery` data 为 `null`） → `navigate('/login', { state: { from: location } })`。
  - loading 中 → 渲染 `<Skeleton />`，不做跳转。
- **只有一处发起跳转**：`useQuery(['auth','me'])` 若返回 401，全局 `onError` 钩子（§ 6.4）负责把 `['auth','me']` 缓存置 `null`；然后 `RequireAuth` 感知到 `null` 后跳转。**RequireAuth 自身不再直接触发新的 `GET /api/auth/me`**——统一由 `useAuth` hook 承担，避免"守卫也发一次、useAuth 也发一次"的重复请求与跳转竞态。
- **管理员路由**：`/admin/*` 在 `<RequireAuth>` 之内再套一层 `<RequireAdmin>`（`user.role === 'admin'` 才放行，否则重定向首页），侧栏「管理后台」入口亦按 role 显隐。前端 role 判断仅控制可见性，真正鉴权由后端 `require_admin` 兜底。管理后台页面（概览/用户/会员/订单）与接口详见 **Spec G（`admin-design.md`）**。

### 3.3 LoginPage（`/login`）
- 左右两栏（Spec F v2 § 5 第 2 屏）：左栏品牌 + 说明句 + 会话策略小字，右栏 24rem 表单。
- 登录 / 注册两个 tab（选中项 2px 赤陶下边框）。
- 两个 Tab 共用字段：`username`（3-32 字符，pattern `^[a-zA-Z0-9_]+$`）、`password`（6-128 字符）。**与 Spec C `UserCredentials` 严格对齐**；边界改动必须两处同步。
- 表单校验：React Hook Form + Zod schema，前端先校验，然后 POST。注册与登录的响应都是 `User` 且都会 `Set-Cookie`（注册即自动登录）。
- 成功后：把用户写入 `queryClient.setQueryData(['auth','me'], user)`，`navigate(from ?? '/', { replace: true })`。
- 失败：`auth.invalid_credentials` / `auth.username_conflict` 用后端 `message` 显示为表单 root 错误；其余错误显示「登录服务暂时不可用，请稍后重试」。

### 3.4 GeneratePage（`/`）与 AssistantPage（学习助手，`/assistant`）

**GeneratePage（结构化出卷，喫茶去 handoff 第 4 屏）**
- 44rem `<textarea>` + 建议 chips + 主按钮「生成试卷」，只做 fresh 模式
  （错题巩固 / 综合复习在错题本页）；非会员显示当日免费次数。
- 点击生成后展开 `PipelineProgress` 四步管线面板（假进度 + 真计时，Spec F v2 § 5）。
- 顶部依据 `GET /api/health/ready` 在题库未就绪时提示。

**AssistantPage（学习助手，与 study-coach agent 的多轮对话）**
- **对话流**：用户消息（右对齐，`accent-wash` 底）与助手回复（无框正文 + 底部细线）交替；助手内容用 **react-markdown + remark-gfm** 渲染（`.chat-md` 样式，支持 GFM 表格）。等待回复时展示赤陶脉冲点「思考中」。
- **建议 chips**：空对话时展示引导标题「学习助手」+ 若干示例（如「来 5 道现在完成时的选择题」「帮我制定 7 天学习计划」），点击即发送。
- **输入区**：底部 `<textarea>`，Enter 发送、Shift+Enter 换行，也有「发送」按钮。
- **新对话**：有消息时右上角出现「＋ 新对话」→ `POST /api/agent/chat/clear` 清空**服务端**该用户的会话历史，并清空本地消息。
- **会话上下文归属**：真正的对话上下文由后端 `SQLiteSession` 按用户维护；**客户端每次只发送本条 `message`**（`POST /api/agent/chat`，见 § 4.3 的 `AgentChatRequest`），不回传历史。前端仅把用于展示的消息列表存进 `sessionStorage`（key `agent.chat`），刷新页面能恢复显示但不参与上下文。
- **开始做题**：当 agent 产出一份试卷时，回复带 `action = { type: 'open_paper', paper_id }`；此时回复下方出现「开始做题 →」按钮，点击 `navigate('/papers/{paper_id}')`。
- 出错时追加一条错误消息「出错了，请稍后重试或换个说法」，并 toast。

### 3.5 PaperPage（试卷详情，`/papers/:paperId`）
做题与复盘同页，按阶段切换。外层 `PaperPageRoute` 以 `key={paperId}` 强制重挂载内层，使 revise 换 id 导航后本地 state（答案、成绩、对话框）自动清空。

- **数据**：`usePaper(paperId)` 拉 `GET /api/papers/{id}`；同时 `getAttemptByPaper(paperId)` 拉上次判分结果（未交卷返回 `null`）。
- **三阶段**：`answering`（未交卷）/ `submitting`（判分中）/ `submitted`（已有结果，本次交卷优先，否则回放历史结果）。
- **卷面**：`PaperSheet` 外壳 + 每题一个 `QuestionCard`。metadata 条由 `RequestSummary`（请求回显）+ `buildPaperNotices(paper.metadata)`（检索缺口 / 改写降级等中文说明）组成；若 metadata 有 `revised_from` 则显示「查看原卷」链接。
- **不显示分数数字**：判分靠卷面上的 ✓/✗、你的答案 vs 正确答案，以及右上角旋转红章 `ScoreStamp`（显示 `correct/total`）。
- **交卷**：底部「交卷」；若有未作答项先弹确认对话框（列出题号，交卷即按错计分）。提交走 `POST /api/attempts`（`buildSubmission` 打包），成功后失效 `['papers','list']`、把结果写入 `['attempt','by-paper',paperId]`，并按结果更新本地错题本（`recordGrade`，仅真实用户）。
- **复盘**：`submitted` 态下每题挂 `SolutionBlock`（见 § 3.9）；答错时把用户答案传给解析。
- **再做一遍**：`GradeBanner` 上的「再做一遍」重置成绩、清空答案、置 `redoing` 忽略历史结果，回到答题态。
- **错题巩固**：`GradeBanner` 上以**当前这份卷答错的题**（考点 + 题型）定向组卷（`POST /api/papers/generate`，`mode: 'remediation'`，带 `wrong_items`）。按钮三态：`错题巩固（N 题）→ 正在组卷… → 跳转试卷 →`（组好后不自动跳转，点击才导航到新卷）。非会员点它会弹升级对话框。
- **重新出卷**：右上角「重新出卷」弹对话框，用一句话让 AI 调整整卷（`POST /api/papers/revise`，返回新 `paper_id` → 导航过去）。非会员功能，带 `MemberPill`。

### 3.6 QuestionCard
根据 `question.question_type` 分派（字段名与 Spec A / Spec C 一致），且有 `answering` / `review` 两态（复盘态展示对错、正确答案与解析槽）：
- `single_choice`：题干 + 四个选项（`question.options`），用户选 `"A"|"B"|"C"|"D"`。
- `word_form`：题干含 `___` 占位 + `hint`（基础词形），一个输入框收变形词。
- `sentence_rewriting`：`original_sentence` + `instruction`（改写要求），有 `template` 时一并渲染作参考框架，输入框收改写结果。

**答案上传结构**：答题草稿 `AnswerDraft` 由 `lib/answers.ts` 的 `buildSubmission` 打包成 `GradeSubmissionItem`（单选传字母；填空/改写传 `blankN` 字典或字符串）。后端 `grading.py` 负责把用户答案与 `Answer`（`str | list[BlankGroup]`）结构比对（Spec C）。

**提交后答案显示**：`GradeResultItem.correct_answer` 为 `AnswerValue`（`string | Array<Record<string,string[]>>`）。前端显示时：`string` 直接展示，候选组数组取第一组各空答案拼接展示。

### 3.7 MasteryPage（`/mastery`）
- 顶部：标题 + 时间窗**分段按钮**（全部记录 / 近 90 / 30 / 7 天，选中 = 赤陶边 + wash 底）。
- 主体：`MasteryReport` 组件，渲染 `MasteryProfile`
  - `weak_kps`（Wilson score 下界最低的若干 KP），每项显示中文考点名（`prettifyKp` 解析）+ `mastery` 分数（等宽字）+ `attempts`。
  - 颜色分级（One Chroma Rule，Spec F v2 § 6）：进度条一律赤陶——`mastery` < 0.4 全饱和（薄弱点更醒目），≥ 0.4 降到 0.45 不透明度；**不用绿/黄/红**。
  - `MasteryProfile` 只含薄弱 KP 概览（`weak_kps` / `dominant_types` / `total_attempts_considered`），不含全部 KP 统计。
- 数据来源：`GET /api/users/me/mastery?window_days=`，TanStack Query key: `['mastery','me',windowKey]`。

### 3.8 PapersPage（`/papers`）与 ReviewPage（`/review`）

**PapersPage（我的试卷）**
- 数据：`GET /api/papers`（只有摘要），`useInfiniteQuery(['papers','list'])`，页大小 20；响应无总数，**满页即认为有下一页**，底部「加载更多」。
- 每行：标题 + meta（生成时间 · 题数）+ 状态章（`submitted` → 已交卷 / 未作答），整行链接到 `/papers/{paper_id}`。（无分数、无满分——见 § 10 与首页原则。）
- 失效时机：生成成功、重新出卷成功、交卷成功三处 `invalidateQueries(['papers','list'])`。
- 空态引导去首页出第一份卷；视觉规则见 Spec F § 5「试卷列表页」。

**ReviewPage（错题复习）**
- 本地错题本：`lib/wrongBook.ts` 按用户存做错的题（交卷时 `recordGrade` 记账，答对清账）；`WrongBookList` 展示，可勾选、删除，并可就地看解析。
- 两个显式出卷入口（`ReviewGeneratePanel` 细线分栏 + `useGeneratePaper`）：
  - **错题巩固**（`mode: 'remediation'`）：以错题本里选中的题定向组卷。
  - **综合复习**（`mode: 'review'`）：按 `review_window_days` 时间窗内答题记录出复习卷。
- 两者都是会员功能：非会员触发 `UpgradeDialog`；出卷共享逻辑与配额见 § 4.4。
- 顶部依据 `GET /api/health/ready`（题库就绪探针）在未就绪时提示「题库正在准备中」。

### 3.9 支撑机制：知识点中文名、解析、学习计划

**知识点中文名（`useKnowledgePoints` + `prettifyKp`）**
- `AppLayout` 挂载时调用 `useKnowledgePoints()`：`GET /api/knowledge-points` 取目录（`staleTime: Infinity`），并**在 render 期间同步**调用 `registerKpNames` 填好 id→中文名映射，使子组件本次渲染就能用 `prettifyKp` 把 KP id 显示为中文名。

**SolutionBlock（单题解析）**
- `question.solution` 已有值直接展示（不请求、不计配额）；否则按需 `POST /api/solutions`，用 `enabled:false` 的 query 缓存住，反复展开/收起不重复请求。
- **答错时把 `user_answer` 一并传入**，让解析定向解释「为什么你选的这个错」。
- 非会员每天限 `FREE_SOLUTION_PER_DAY` 次 AI 解析，用尽后提示开通会员。

**StudyPlanPage（学习计划，`/study-plan`）**
- 展示最新一份学习计划：`GET /api/agent/study-plans/latest`（`useQuery(['study-plan','latest'])`，无计划返回 `null` → 空态引导去学习助手制定）。
- 顶部显示总天数与起始日期。每天一行 `DayRow`（细线行式，无卡片）：DAY 序号 + 主题（`theme`）+ 题型标签 + **当天可覆盖多个知识点**（`kp_names` 中文标签）+ 当天总题量（`total_questions`）+ 可选日期/备注 + 「开始练习 →」链接到当天预生成的 `paper_id`。

### 3.10 MembershipPage（会员 / 支付，`/membership`）
- 与独立支付小服务通信（`payment/`，dev 经 `/payapi` 代理到 `:8001`）。
- 展示会员状态（`GET /payapi` 会员查询）、套餐列表（`getPlans`）、权益对比表；下单 `createOrder(planId, channel)`：`mock_pay` 模式走扫码弹窗（`PayQrDialog`，带模拟支付按钮），真实沙盒走网页收银台。均为模拟支付，不产生真实扣款。

---

## 4. 状态管理

### 4.1 TanStack Query 用法
- 所有服务端状态通过 `useQuery` / `useMutation`。
- 默认配置（`lib/queryClient.ts`）：
  - `staleTime: 30_000`（试卷、掌握度在 30s 内不重取）。
  - `retry: (failureCount, error) => 非 401 且 failureCount < 2`。
  - `refetchOnWindowFocus: false`。
- Query keys 约定：
  - `['auth', 'me']` — 当前用户
  - `['paper', paperId]` — 单份试卷
  - `['papers', 'list']` — 试卷列表（PapersPage 的 `useInfiniteQuery`；生成 / 重出 / 交卷成功后 invalidate）
  - `['attempt', 'by-paper', paperId]` — 某试卷的上次判分结果（复盘回放；交卷成功后写入）
  - `['mastery', 'me', windowKey]` — 掌握度报告（按时间窗）
  - `['knowledge-points']` — 知识点目录（`staleTime: Infinity`）
  - `['study-plan', 'latest']` — 最新学习计划
  - `['payMembership']` / `['payPlans']` / `['payHealth']` — 支付小服务状态（与会员页、`useMembership` 共享）

### 4.2 UI 状态
- `answers: Record<number, AnswerDraft>` — key 为 `PaperItem.index`（1-based）。用 `index` 而非 question id，因为 `RevisedQuestion` 没有 id 字段（改题后不再是题库原题）。
- 学习助手的消息列表 — AssistantPage local state，另存 `sessionStorage`（仅展示，非上下文）。
- 表单状态 — React Hook Form。
- 对话框、折叠、重做态等 — 各组件 / 页面 local state。

### 4.3 类型对齐策略
- `src/types/api.ts` 手写与 Spec C 对齐的类型（`Paper`、`PaperItem`、`RevisedQuestion`、`GradeSubmissionRequest/Response`、`MasteryProfile`、`KPMastery`、`KnowledgePoint`、`AgentChatRequest/Response`、`AgentAction`、`StudyPlan`/`StudyPlanDay`、`ErrorResponse` 等）；支付小服务类型放 `src/types/payment.ts`。
- 后端契约变更时，人工同步这些文件。**不引入 OpenAPI 自动生成**（MVP 简化）。
- 学习助手对话上下文由后端 `SQLiteSession` 维护，故 `AgentChatRequest` 只含 `message`，不含 history。

### 4.4 会员门槛与免费配额
- `useMembership()`（基于 `['payMembership']`）给出 `isMember` / `locked` / `expiresAt`。**加载中不锁**（避免会员看到锁标闪烁）；**支付服务出错时按会员处理（不锁）**——联调期的开发便利，避免功能被支付服务不可用阻断。仅明确返回 `active:false` 才 `locked`。
- `useGeneratePaper()` 封装出卷共享逻辑：成功后种缓存零请求进卷、失效列表、非会员扣当日配额、导航到新卷；`ai.parser_failed` / `ai.no_candidate` 走表单内提示，其余 toast。
- 非会员每日免费配额（`lib/quota.ts`，本地计数）：`FREE_GENERATE_PER_DAY` 次出卷、`FREE_SOLUTION_PER_DAY` 次 AI 解析；错题巩固 / 综合复习 / 重新出卷为纯会员功能，触发 `UpgradeDialog`。

---

## 5. API 客户端

### 5.1 fetch 封装（`api/client.ts`）
一个内部 `fetchJson(base, path, opts)` 承担实际请求，导出两个入口：`apiFetch`（`base='/api'`，主后端）与 `payFetch`（`base='/payapi'`，支付小服务）。

```ts
// 伪代码
async function fetchJson<T>(base: string, path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...opts,
    credentials: 'include',              // 携带 Cookie
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
  })
  if (res.status === 204) return undefined as T
  let body: unknown
  try {
    body = await res.json()
  } catch {
    // 非 JSON 响应（如代理层 502 的 HTML）：合成一个 server.internal 错误体
    body = { error_code: 'server.internal', message: `服务响应异常（HTTP ${res.status}）`, detail: null, trace_id: '' }
  }
  if (!res.ok) throw new ApiError(res.status, body as ErrorResponse)
  return body as T
}

export const apiFetch = <T>(path: string, opts?: RequestInit) => fetchJson<T>('/api', path, opts)
export const payFetch = <T>(path: string, opts?: RequestInit) => fetchJson<T>('/payapi', path, opts)
```

### 5.2 ApiError
```ts
export class ApiError extends Error {
  constructor(
    public status: number,
    public payload: ErrorResponse
  ) {
    super(payload.message);
  }
}
```

### 5.3 错误分派（`lib/errors.ts`）
错误码严格对齐 Spec C § 6.2 的稳定清单：

- `auth.unauthorized`（401） → 清 `['auth','me']` 缓存 + 跳 `/login`（通过 § 6.4 的 `window.__appNavigate`）。
- `auth.invalid_credentials`（401） → 停留在登录页，直接用 `payload.message` 展示。
- `auth.username_conflict`（409） → 停留在注册页，直接用 `payload.message` 展示。
- `rate.exceeded`（429） → toast "请求过于频繁，请稍后再试"。
- `resource.not_found`（404） → toast `payload.message`。
- `request.invalid`（422） → toast `payload.message`（表单相关字段错误已被前端 Zod 提前拦截，走到这里通常是意外）。
- `ai.*`（400/422/500/502） → toast `payload.message`；其中 `ai.llm_upstream` 提示 "AI 服务暂时不可用，稍后重试"。
- `server.internal`（5xx 兜底） → toast "服务暂时不可用"，附 `payload.trace_id` 便于用户反馈。
- 其它未知 `error_code` → 直接用 `payload.message` 展示。

### 5.4 模块化 API 函数
每个模块（`auth.ts`、`papers.ts` 等）导出对应端点的函数，参数用 Spec C 里的请求模型类型。示例：
```ts
// api/papers.ts
export const generatePaper = (req: GeneratePaperRequest) =>
  apiFetch<Paper>('/papers/generate', {
    method: 'POST',
    body: JSON.stringify(req),
  });
```

---

## 6. 鉴权与路由守卫

### 6.1 登录状态识别
- 后端设置 httpOnly Cookie `session_id`（Spec C § 5）。
- 前端**看不到** Cookie 内容；判断登录状态靠 `GET /api/auth/me`。
- `useAuth()` hook 包装 `useQuery(['auth', 'me'], fetchMe)`。

### 6.2 登录流程
1. 用户在 LoginPage 提交表单。
2. `POST /api/auth/login` 成功 → 后端 `Set-Cookie` → 浏览器自动保存。
3. 前端调用 `queryClient.invalidateQueries(['auth', 'me'])` → 触发重新拉取。
4. `useAuth` 拿到用户对象 → RequireAuth 放行 → 跳转 `from` 或 `/`。

### 6.3 登出流程
- 侧栏底部（用户名下方）"登出" 链接 → `POST /api/auth/logout` → `queryClient.clear()` → `navigate('/login')`。

### 6.4 全局 401 处理
`queryClient` 的 `defaultOptions.queries.onError` 与 `mutations.onError` 中：
```ts
if (error instanceof ApiError && error.status === 401) {
  queryClient.setQueryData(['auth', 'me'], null);
  // 通过挂在 window 上的 router navigate 引用统一跳转，避免与 § 3.2 的 navigate 行为分叉
  window.__appNavigate?.('/login');
}
```
说明：`window.__appNavigate` 由 `App.tsx` 在挂载时用 `useNavigate()` 结果赋值，保证与 React Router 一致的跳转行为（history 而非整页刷新）。

---

## 7. 组件库

### 7.1 shadcn/ui 使用清单
以下组件通过 `npx shadcn-ui@latest add <name>` 生成到 `src/components/ui/`：
- Button, Input, Textarea, Label
- Card, Dialog, Tabs, Select, RadioGroup
- Toast（错误 / 成功提示）
- Skeleton（加载态）

### 7.2 自定义组件
- `Sidebar` / `AppLayout`（左侧可折叠导航外壳）、`GenerateForm`、`PipelineProgress`、
  `QuestionCard`（+ `question-fields/*`）、`AnswerCard`（粘顶答题卡）、`GradeBanner`、
  `SolutionBlock`、`MasteryReport`、`RequestSummary`、`RequireAuth`、
  `review/WrongBookList`、`review/ReviewGeneratePanel`、`UpgradeDialog`（含 `MemberPill`）、`PayQrDialog`。
- 所有自定义组件禁止直接调用 `fetch`，只通过 hooks 消费 `api/` 层。

### 7.3 样式（2026-07-27 随喫茶去改版更新）
- Tailwind v4 原子类；设计 tokens 来自设计交接包，原样拷入
  `src/styles/{colors,typography,spacing,base}.css`，由 `index.css` 的
  `@theme inline` 映射为语义类并接管 shadcn 变量（见 Spec F v2 § 2）。
- 不引入额外 CSS 框架；组件里禁止写死颜色，只用语义类 / token。

---

## 8. 配置

### 8.1 `vite.config.ts`
```ts
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },     // 主后端
      '/payapi': { target: 'http://localhost:8001', changeOrigin: true },  // 支付小服务
    },
  },
  build: { outDir: 'dist', sourcemap: true },
});
```
（Tailwind 通过 `@tailwindcss/vite` 插件接入，无独立 `tailwind.config.js`。）

### 8.2 环境变量
- MVP 不需要环境变量：dev 用 proxy，prod 同源。
- 如果未来需要指向不同后端（如预发布环境），再引入 `VITE_API_BASE_URL`。

### 8.3 构建产物路径
- `vite build` 输出到 `frontend/dist/`。
- 后端启动脚本用 `StaticFiles(directory="frontend/dist", html=True)` 挂到 `/`。

---

## 9. 前端组件测试

### 9.1 测试范围（本 Spec 层）
- **组件单元测试**：QuestionCard 三种题型渲染（答题/复盘两态）、GenerateForm 提交、MasteryReport 颜色映射、RequireAuth 未登录跳转、ApiError 分派。
- **不含**：真实后端调用、真实 LLM。所有 API 调用用 `msw`（Mock Service Worker）拦截。

### 9.2 工具链
| 工具 | 用途 |
|------|------|
| Vitest | 测试运行器 |
| @testing-library/react | 组件渲染 + 交互模拟 |
| @testing-library/user-event | 更真实的键盘/鼠标事件 |
| msw | HTTP mock（浏览器 & Node 环境都可用） |

### 9.3 组织方式
- 每个组件旁边一个 `.test.tsx`，例如 `QuestionCard.test.tsx`。
- msw handlers 放 `src/mocks/handlers.ts`，测试 setup 里 `beforeAll(() => server.listen())`。
- 一份 golden fixture：`src/mocks/fixtures/paper.golden.json`，与 Spec E 共享。

### 9.4 覆盖率目标
- 行覆盖 ≥ 70%，关键组件（QuestionCard、GenerateForm、RequireAuth）≥ 90%。
- 覆盖率不作为门禁，只作为参考。

### 9.5 与 Spec E 的边界
- 本 Spec 的测试**只跑单个组件**，msw mock 掉 API。
- Spec E 定义的 e2e 才会启动真实前端 + 真实后端 + mock LLM 全链路。

---

## 10. 非目标（MVP 不做）

1. 移动端适配（只保证 1280×720 以上桌面浏览器）。
2. 国际化（中文硬编码）。
3. ~~深色模式~~（2026-07-27 已随喫茶去 token 低成本实现：设置页「阅读外观」切换 `.dark`，持久化 localStorage）。
4. 试卷 PDF 导出。
5. ~~试卷列表页~~（2026-07-11 已实现，见 § 3.7）。
6. 草稿保存（刷新页面丢失中间答题状态）。
7. 富文本 / LaTeX（英语题目全部纯文本）。
8. 无障碍（accessibility）深度优化，只做 shadcn/ui 内置的 ARIA。
9. 埋点 / 分析（Sentry、GA 等）。

---

## 10.5 功能拆分改版（2026-08-06）

单一自然语言入口拆为分层多入口,全部出卷入口共用一根管道
「结构化选择 → `lib/composeQuery.ts` 确定性拼句(措辞对齐 `ai_engine/prompts/parser.md`)
→ `useGeneratePaper` → `POST /api/papers/generate`」:

- **路由**:`/` 双态(`HomeGate`:匿名=营销首页、登录=工作台、admin 重定向);
  原生成页迁 `/generate`(一句话出卷);新增 `/practice`(练习中心 hub)、
  `/practice/:slug`(题型专项 ×9,`lib/drillConfig.ts` 一模板九配置)、
  `/practice/custom`(自选组卷工坊)、`/mock`(整卷模拟 5 配方 + 纯前端限时);
  `/welcome` 重定向 `/`。路径常量集中 `lib/paths.ts`,侧栏数据 `lib/nav.ts`(三组九项)。
- **新增能力**:强度三档显式控件(真题档会员)、按考点专练(隐藏 0 题 KP、
  8 个薄尾 KP 预警)、主题出卷(仅语法,自动升 fresh)、每日一练(按星期配方)、
  中考倒计时(`lib/examDate.ts` + 设置页)、打印分版(学生卷免费/教师版含参考答案
  会员,Tailwind `print:` 变体)、学情报告(会员,`StudyReport.tsx`)、
  shortfall 行动提示(试卷页)、学习计划空态预填学习助手。
- **定价单一来源**:`lib/pricing.ts` 静态镜像 payment PLANS + 共享 BENEFITS
  (营销首页匿名展示与会员页共用;购买路径仍走 `getPlans()` 实时数据)。
- **配额**:所有 fresh 入口共享一个 `'generate'` 池(3 次/天,不按入口拆分)。
- 前置后端修复:`ai_engine/parser.py` 白名单补齐两个阅读题型(独立提交)。

---

## 11. 开放问题（记录，不阻塞实现）

1. **未提交试卷刷新丢失答案**：MVP 接受。若用户反馈强烈，后续加 `sessionStorage` 草稿保存。
2. **试卷长度上限**：题目 > 100 时前端渲染性能是否 OK？后端已有硬上限（Spec C），前端等真实测量。
3. **移动端**：等看是否有实际需求。
4. **（2026-07-27，设计交接包指出的后端缺口）错题聚合端点缺失**：spec C 没有
   「按用户聚合错题」的端点，当前错题本是前端 localStorage 记账（仅本设备）。
   建议后端新增 `GET /api/users/me/wrong-items?window_days=`，前端即可换成服务端错题本。
5. **（同上）题库只读检索端点缺失**：handoff 第 10 屏「题库浏览」需要
   `GET /api/questions?…`（搜索 + 题型/难度筛选），端点就绪后按 Spec F v2 § 5 表格补屏。
6. **（同上）`GET /api/papers` 摘要无得分字段**：历史试卷列表只能显示
   「已交卷 / 未作答」，无法显示「已交 45/60」。

---

## 12. 里程碑 M6（前端 MVP）

**M6 完成标准**：
1. `frontend/` 目录搭好，`npm run dev` + 已跑通的后端 → 完成登录、在学习助手对话出卷、进卷做题、交卷、复盘（✓/✗ + 红章 + 解析）、看掌握度全流程。
2. QuestionCard、GenerateForm、RequireAuth 组件测试全绿。
3. `vite build` 产物被后端 StaticFiles 挂载后，浏览器访问 `http://localhost:8000/` 与 dev 模式行为一致。

依赖：M5（后端 MVP）已完成。

---

## 13. 不变量（Invariants）

前端必须始终保证：

1. **单一数据源**：任何服务端数据都通过 TanStack Query，不做手动 useState 缓存副本。
2. **HTTP 只走 `api/` 层**：组件不直接 `fetch`。
3. **Cookie 由浏览器管理**：前端代码不读、不写 Cookie。
4. **401 必跳登录**：不能吞掉 401 让用户看到空白页。
5. **类型对齐**：`types/api.ts` 与 Spec C 契约保持同步，变更时人工审核。
6. **无隐式服务器状态**：任何"当前试卷"、"当前掌握度"必须从 Query cache 获得，不复制到 Context 或全局 store。

# 前端设计（Spec D）

> 面向对象：中考英语试卷生成器的 Web 前端。
> 依赖：[Spec A（题库摄入）](./2026-07-07-question-bank-ingestion-design.md)、[Spec B（AI Engine）](./2026-07-07-ai-engine-design.md)、[Spec C（后端）](./2026-07-07-backend-design.md)。
> 后置：[Spec E（跨系统测试）](./2026-07-07-testing-design.md)（待写）。

---

## 0. 范围与依赖

### 0.1 本 Spec 负责
- 浏览器端应用（用户交互层）。
- 三个页面：**登录页 / 主页 / 掌握度页**。
- 与后端（Spec C）之间的 HTTP 调用契约的**消费方**约定（不定义契约，契约在 Spec C）。
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
- **开发时**：Vite dev server（`localhost:5173`） + FastAPI（`localhost:8000`），Vite 配置 `/api` 代理到 8000，避开 CORS。
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
| 组件测试 | Vitest + @testing-library/react |
| 代码质量 | ESLint + Prettier + TypeScript strict |

### 2.2 目录结构
```
frontend/
  index.html
  vite.config.ts
  tsconfig.json
  tailwind.config.js
  package.json
  src/
    main.tsx                 # React 入口，挂载 <App/>
    App.tsx                  # 路由 + Providers（QueryClient、Router）
    routes.tsx               # 路由表 + Guard
    types/
      api.ts                 # 与 Spec C 对齐的 TS 类型（手写）
    api/
      client.ts              # fetch 封装 + 错误映射
      auth.ts                # login/register/logout/me
      papers.ts              # generate/revise/get/list
      solutions.ts           # 解析获取
      attempts.ts            # 提交答题
      mastery.ts             # 掌握度
    pages/
      LoginPage.tsx
      HomePage.tsx           # 生成 + 做题 + 提交
      MasteryPage.tsx        # 掌握度报告
    components/
      ui/                    # shadcn/ui 生成的组件
      PaperView.tsx          # 试卷渲染
      QuestionCard.tsx       # 单题渲染（单选/填空）
      GenerateForm.tsx       # 自然语言 + 面板混合表单
      MasteryTree.tsx        # 知识点树
    hooks/
      useAuth.ts             # 当前用户
      useCurrentPaper.ts     # 当前试卷缓存
    lib/
      queryClient.ts
      errors.ts              # ErrorResponse → 用户可读文本
```

### 2.3 TypeScript 配置要点
- `strict: true`，`noUncheckedIndexedAccess: true`。
- `paths` 别名：`@/` → `src/`。
- 依赖版本在 `package.json` 中固定次版本（`^` 而非 `*`）。

---

## 3. 页面与路由

### 3.1 路由表
| 路径 | 页面 | 是否需登录 | 说明 |
|------|------|-----------|------|
| `/login` | LoginPage | 否 | 登录 + 注册（切换 tab） |
| `/` | HomePage | 是 | 生成试卷 + 做题 + 提交 |
| `/mastery` | MasteryPage | 是 | 用户掌握度报告 |
| `*` | 重定向到 `/` | — | 未匹配的 URL |

### 3.2 路由守卫
- 使用 `<RequireAuth>` 高阶组件包裹需要登录的路由：
  - 挂载时读 `useAuth()`（内部是 `useQuery(['auth','me'])`）。
  - 已有用户对象 → 渲染 children。
  - 无用户对象（`useQuery` data 为 `null`） → `navigate('/login', { state: { from: location } })`。
  - loading 中 → 渲染 `<Skeleton />`，不做跳转。
- **只有一处发起跳转**：`useQuery(['auth','me'])` 若返回 401，全局 `onError` 钩子（§ 6.4）负责把 `['auth','me']` 缓存置 `null`；然后 `RequireAuth` 感知到 `null` 后跳转。**RequireAuth 自身不再直接触发新的 `GET /api/auth/me`**——统一由 `useAuth` hook 承担，避免"守卫也发一次、useAuth 也发一次"的重复请求与跳转竞态。

### 3.3 LoginPage（`/login`）
- 一个 `<Tabs>`：**登录 / 注册**。
- 两个 Tab 共用字段：`username`（3-32 字符，pattern `^[a-zA-Z0-9_]+$`）、`password`（6-128 字符）。**与 Spec C § 2.1 `UserCredentials` 严格对齐**；边界改动必须两处同步。
- 表单校验：React Hook Form + Zod schema，前端先校验，然后 POST。
- 成功后：`navigate(from ?? '/')`。
- 失败：显示后端返回的 `ErrorResponse.message`（不额外解释错误码）。

### 3.4 HomePage（`/`）
分三区，纵向排列：

**Ⅰ. GenerateForm（生成区）**
- 一个大 `<Textarea>`，placeholder：`"例如：给我出 20 道八年级下册被动语态的选择题"`。
- 一行面板控件（简化，非硬约束）：模式选择 `<Select>`（新生成 / 错题巩固 / 综合复习）。
- 一个 `<Button>` "生成试卷"。
- 提交时：
  - 模式 = 新生成 → `POST /api/papers/generate`，body 只含 `user_query`。
  - 模式 = 错题巩固 → 附带当前刚提交完试卷的 `wrong_items`。
  - 模式 = 综合复习 → 附带 `review_window_days=30`。
- 返回的 `Paper` 存入 TanStack Query 缓存（key: `['paper', paperId]`），滚动到试卷区。

**Ⅱ. PaperView（试卷区）**
- 顶部 metadata 条：标题、生成时间、题目数量。
- 一个 "重新出" 按钮：弹 `<Dialog>` 输入修改意图 → `POST /api/papers/revise`（body: `{ paper_id, user_instruction }`，Spec C § 5.1）→ 后端返回新的 `Paper`（`paper_id` 换新）→ 更新缓存里的当前试卷引用。
- 试卷题目列表：每题一个 `QuestionCard`。
- 底部 "提交" 按钮：把答案打包成 `GradeSubmissionRequest` → `POST /api/attempts` → 展示 `GradeSubmissionResponse`。

**Ⅲ. GradeResult（成绩区，提交后展开）**
- 总分、正误列表。
- 每题一个 "查看解析" 按钮 → `POST /api/solutions` → 展开解析内容。
- 一个 "错题巩固" 按钮 → 触发 GenerateForm 的 remediation 模式（预填入错题 refs）。**该按钮只在当前会话内、当次提交后有效**：刷新页面即失效（MVP 不持久化 wrong_items 列表）。

### 3.5 QuestionCard
根据 `question.question_type` 分派（字段名与 Spec A § 2.2 / § 2.3 一致）：
- `single_choice`：题干 + `<RadioGroup>`（4 个选项，来自 `question.options`）。用户选择结果 `"A" | "B" | "C" | "D"` 作为 `user_answer`。
- `word_form`：渲染 `stem`（含 `___` 占位符）+ `hint`（给出的基础词形）。把 `___` 替换为一个 `<Input>`，用户输入变形后的词作为 `user_answer`。
- `sentence_rewriting`：渲染 `original_sentence`（原句）+ `instruction`（改写要求），若有 `template` 则一并渲染作为参考框架。提供一个 `<Input>` 供用户填写改写结果，作为 `user_answer`。

**答案上传结构**：所有题型统一按 Spec C § 2.2 的 `GradeSubmissionItem = { index, user_answer: string }` 上传；单选传 label，填空传字符串，无 `string[]` 变体。后端 `grading.py` 负责将用户字符串与 `Answer`（`str | list[BlankGroup]`）结构比对（见 Spec C § 5.2）。

**提交后答案显示**：`GradeResultItem.correct_answer` 类型为 `Answer`（`string | BlankGroup[]`，见 Spec C § 2.3）。前端显示时：`string` 直接展示，`BlankGroup[]` 取第一个候选组的各空答案拼接展示（如 `"so / that"`）。

### 3.6 MasteryPage（`/mastery`）
- 顶部：用户名 + 总答题数 + 综合正确率。
- 主体：`MasteryTree` 组件
  - 按知识点树层级折叠。
  - 每个叶子节点显示：`mastery`（Wilson score 下界，格式化为百分比）+ `attempts`（做题次数）。
  - 颜色标记：`mastery` ≥ 0.7 绿；0.4–0.7 黄；< 0.4 红。
  - 注：`MasteryProfile` 只含 `weak_kps`（掌握度最低的前 8 个 KP），不含全部 KP 的统计。`MasteryTree` 只渲染这 8 个，其余 KP 暂不展示（MVP）。
- 数据来源：`GET /api/users/me/mastery`，TanStack Query key: `['mastery', 'me']`。

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
  - `['papers', 'list']` — 试卷列表（暂不用页面，为未来预留）
  - `['mastery', userId | 'me']`

### 4.2 UI 状态
- `answers: Record<number, string>` — key 为 `PaperItem.index`（1-based），value 为用户答案字符串。用 `index` 而非 question id，因为 `RevisedQuestion` 没有 id 字段（改题后不再是题库原题）。
- 表单状态 — React Hook Form。
- 对话框、折叠等 — 各组件 local state。

### 4.3 类型对齐策略
- `src/types/api.ts` 手写与 Spec C 对齐的类型（`Paper`、`PaperItem`、`RevisedQuestion`、`GradeSubmissionRequest/Response`、`MasteryProfile`、`KPMastery`、`ErrorResponse` 等）。
- 每个类型顶部注释说明"对齐 Spec C § X.Y"。
- 后端契约变更时，人工同步这个文件。**不引入 OpenAPI 自动生成**（MVP 简化）。

---

## 5. API 客户端

### 5.1 fetch 封装（`api/client.ts`）
```ts
// 伪代码
export async function apiFetch<T>(
  path: string,
  opts?: RequestInit
): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...opts,
    credentials: 'include',              // 携带 Cookie
    headers: {
      'Content-Type': 'application/json',
      ...opts?.headers,
    },
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json();
  if (!res.ok) throw new ApiError(res.status, body as ErrorResponse);
  return body as T;
}
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
- 顶部导航栏一个 "登出" 按钮 → `POST /api/auth/logout` → `queryClient.clear()` → `navigate('/login')`。

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
- `PaperView`, `QuestionCard`, `GenerateForm`, `MasteryTree`, `RequireAuth`, `AppNav`。
- 所有自定义组件禁止直接调用 `fetch`，只通过 hooks 消费 `api/` 层。

### 7.3 样式
- Tailwind 原子类，`tailwind.config.js` 用 shadcn/ui 默认主题。
- 不引入额外 CSS 框架。

---

## 8. 配置

### 8.1 `vite.config.ts`
```ts
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
```

### 8.2 环境变量
- MVP 不需要环境变量：dev 用 proxy，prod 同源。
- 如果未来需要指向不同后端（如预发布环境），再引入 `VITE_API_BASE_URL`。

### 8.3 构建产物路径
- `vite build` 输出到 `frontend/dist/`。
- 后端启动脚本用 `StaticFiles(directory="frontend/dist", html=True)` 挂到 `/`。

---

## 9. 前端组件测试

### 9.1 测试范围（本 Spec 层）
- **组件单元测试**：QuestionCard 三种题型渲染、GenerateForm 提交、MasteryTree 颜色映射、RequireAuth 未登录跳转、ApiError 分派。
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
3. 深色模式。
4. 试卷 PDF 导出。
5. 试卷列表页（Spec C 的 `/api/papers` 接口保留，但前端不做 UI）。
6. 草稿保存（刷新页面丢失中间答题状态）。
7. 富文本 / LaTeX（英语题目全部纯文本）。
8. 无障碍（accessibility）深度优化，只做 shadcn/ui 内置的 ARIA。
9. 埋点 / 分析（Sentry、GA 等）。

---

## 11. 开放问题（记录，不阻塞实现）

1. **未提交试卷刷新丢失答案**：MVP 接受。若用户反馈强烈，后续加 `sessionStorage` 草稿保存。
2. **试卷长度上限**：题目 > 100 时前端渲染性能是否 OK？后端已有硬上限（Spec C），前端等真实测量。
3. **移动端**：等看是否有实际需求。

---

## 12. 里程碑 M6（前端 MVP）

**M6 完成标准**：
1. `frontend/` 目录搭好，`npm run dev` + 已跑通的后端 → 完成登录、生成一份试卷、做题、提交、看成绩、看解析、看掌握度全流程。
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

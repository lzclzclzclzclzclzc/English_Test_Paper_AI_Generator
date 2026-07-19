# 前端联调与测试使用手册

本文给前端和测试同学使用。完整字段可参考 [后端 API 协作手册](./backend-api.md) 与 Swagger：`http://127.0.0.1:8000/docs`。

## 联调方式选择

| 场景 | 后端运行位置 | 前端使用方式 | 是否需要 Key/模型 |
|---|---|---|---|
| 日常页面开发 | 每位同学自己的电脑 | 请求各自的 `127.0.0.1:8000` | 不需要，使用 `test` 模式 |
| 真实 AI 质量验收 | 后端负责人的电脑 | 访问负责人分享的同源 HTTPS 地址 | 仅负责人机器需要 |

`127.0.0.1` 只表示当前电脑；前端同学从 Git 拉取代码后，需要在**自己的电脑**启动一份 `test` 后端。异地联调不要让本地前端直接跨站调用临时公网 API；登录 Cookie 需要同源访问才稳定。请使用 [远程同源部署指南](./remote-frontend-deployment.md)。

## 1. 最快联调：离线测试模式

前端页面开发、登录、做题、交卷和历史记录联调不需要 API key 或 embedding 模型。

在项目根目录创建/修改 `.env`：

```env
BACKEND_ENV=test
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
# 若 Vite 不在默认 5173 端口运行，同步修改为前端实际 Origin。
FRONTEND_ORIGIN=http://localhost:5173
```

启动后端：

```powershell
python -m backend.cli init-db
python -m backend.cli serve --reload
```

此模式下 `POST /api/papers/generate` 返回稳定的离线试卷 fixture；其余鉴权、保存、判分、掌握度和限流逻辑与正式接口一致。不要把 test 模式当作题目质量验收。

后端在 `test` 与 `development` 模式均会仅允许 `FRONTEND_ORIGIN` 指定的本地前端 Origin 携带 Cookie；前端端口变更时必须同步更新该变量。

## 2. 真实 AI 模式

需要验证生成质量时，调整 `.env`：

```env
BACKEND_ENV=development
FRONTEND_ORIGIN=http://localhost:5173
LLM_API_KEY=填入本机有效密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

普通请求只会走 SQLite 检索；带明显场景语义的请求会触发向量检索，需额外完成：

```powershell
python models/download_model.py
```

模型未下载或向量库不可用时，不要发送场景型请求；先用“来 3 道单选题”这类普通请求验证主流程。CPU 环境下向量检索会比较慢。

## 3. 前端请求约定

开发期 API 地址为**当前开发者自己电脑**的 `http://127.0.0.1:8000/api`。所有受保护请求必须带 Cookie：

```ts
const api = async (path: string, options: RequestInit = {}) => {
  const response = await fetch(`http://127.0.0.1:8000/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!response.ok) throw await response.json();
  return response.status === 204 ? undefined : response.json();
};
```

登录/注册成功后服务端设置 `session_id` 的 httpOnly Cookie，前端不能也不需要读取它。刷新页面时调用 `GET /auth/me` 恢复登录态；收到 `auth.unauthorized` 时跳转登录页。

## 4. 推荐调用顺序

1. `POST /auth/register` 或 `POST /auth/login`
2. `POST /papers/generate` 生成并保存试卷
3. 使用响应中的 `items` 渲染题目
4. `POST /attempts` 一次性提交整份试卷答案
5. `GET /users/me/mastery` 展示薄弱点
6. 可选：`POST /solutions` 请求某一道题的解析；`POST /papers/revise` 按自然语言修改整卷

## 5. 核心接口示例

### 生成试卷

```ts
const paper = await api('/papers/generate', {
  method: 'POST',
  body: JSON.stringify({
    user_query: '来 3 道单项选择题',
    mode: 'fresh',
  }),
});
```

`mode` 可取 `fresh`、`remediation`、`review`。错题巩固传 `wrong_items`；复习模式可传 `review_window_days`。

`paper.metadata.stage_ms` 和 `paper.metadata.vector_retrieval` 仅用于开发调试。UI 必须容忍 `metadata` 字段不存在或新增。

### 渲染和提交答案

| 题型 | `question_type` | 前端输入 | `user_answer` 示例 |
|---|---|---|---|
| 单项选择 | `single_choice` | 单选按钮 | `"B"` |
| 词性转换 | `word_form` | 单个文本框 | `"written"` |
| 句子改写 | `sentence_rewriting` | 按 blank 顺序的多个文本框 | `{"blank1":"so","blank2":"that"}` |

```ts
const result = await api('/attempts', {
  method: 'POST',
  body: JSON.stringify({ paper_id: paper.paper_id, items: answers }),
});
```

提交必须包含且只包含该试卷的每一个 `index` 一次；缺题、重复题号或陌生题号返回 `request.invalid`。

### 请求解析和改卷

```ts
await api('/solutions', {
  method: 'POST',
  body: JSON.stringify({
    question: paper.items[0].question,
    source_question_id: paper.items[0].source_question_id,
    revision_mode: paper.items[0].revision_mode,
  }),
});

const revised = await api('/papers/revise', {
  method: 'POST',
  body: JSON.stringify({
    paper_id: paper.paper_id,
    user_instruction: '把题目改得简单一点',
  }),
});
```

改卷成功后会返回新的 `paper_id`；前端应切换到新试卷，不覆盖旧试卷的历史记录。

## 6. 前端测试清单

- 注册、登出、重新登录和刷新后恢复登录态。
- 未登录访问受保护接口时跳登录页。
- 生成、读取历史列表、读取单张试卷。
- 三种题型的输入、完整提交、错误答案展示。
- 缺题/重复提交返回 `request.invalid` 的提示。
- `429 rate.exceeded` 显示“稍后重试”；`502 ai.llm_upstream` 提供重试入口；错误展示可记录响应的 `trace_id`。
- 在离线 test 模式完成流程测试，再在真实 AI 模式做少量生成质量验收。
- 不要把负责人电脑的 `127.0.0.1` 写进前端配置；该地址在每个人电脑上都指向自己。

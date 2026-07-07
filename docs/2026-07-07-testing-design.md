# 跨系统测试设计（Spec E）

> 面向对象：整个中考英语试卷生成器系统的**跨模块 / 端到端**测试策略。
> 依赖：[Spec A（题库摄入）](./2026-07-07-question-bank-ingestion-design.md)、[Spec B（AI Engine）](./2026-07-07-ai-engine-design.md)、[Spec C（后端）](./2026-07-07-backend-design.md)、[Spec D（前端）](./2026-07-07-frontend-design.md)。

---

## 0. 范围

### 0.1 本 Spec 负责
- **测试全景图**：明确四层测试的边界与责任。
- **跨模块测试**（AI Engine ↔ 后端 ↔ 前端 端到端）。
- **共享测试基础设施**：LLM Mock、golden fixtures、测试数据种子。
- **CI 流水线**：哪些层在什么时机跑。

### 0.2 本 Spec 不负责
- 单模块内部的单元测试细节：见各模块 Spec 的 "Tests" 节
  - Spec A § 7（题库摄入单元测试）
  - Spec B § 11（AI Engine 单元测试）
  - Spec C § 10（后端集成测试）
  - Spec D § 9（前端组件测试）

### 0.3 与前面 Spec 的关系
本 Spec 不覆盖任何前面 Spec 的决策，只把散落在各 Spec 中的测试策略**串起来**并补齐**跨系统**部分。

---

## 1. 测试全景图

### 1.1 四层结构（复述 Spec C § 0.3 的确认决策）

| 层 | 范围 | 工具 | 是否 mock LLM | 归属 Spec |
|----|------|------|---------------|-----------|
| L1 单元测试 | 单函数 / 单类 | pytest / Vitest | 是（打桩） | A/B/C/D |
| L2 后端集成测试 | FastAPI + SQLite + AI Engine（真实拼装） | pytest + httpx | 是（monkeypatch DeepSeek client） | C |
| L3 前端组件测试 | 单页面 / 单组件，msw 拦截 HTTP | Vitest + testing-library + msw | 是（msw 返回 fixture） | D |
| L4 端到端（e2e） | 真浏览器 → 真前端 → 真后端 → mock LLM | Playwright | 是（后端启动前替换 DeepSeek client） | **本 Spec** |

**Spec E 主要负责 L4**，并定义 L2/L3/L4 共享的 mock 与 fixture。

### 1.2 决策：e2e 全部 mock LLM
- 与 Spec C § 0.3 一致。
- 理由：CI 稳定性 > 真 LLM 覆盖率。真 LLM 的行为已在 AI Engine 的 golden set 回归（Spec B § 10）里以离线方式覆盖。
- 例外：一个**手动触发的**"live smoke"任务，跑一次真 DeepSeek，见 § 6.4。

---

## 2. 共享测试基础设施

### 2.1 目录布局（monorepo 视角）
```
/
  backend/
    tests/                    # L1 + L2
  frontend/
    src/**/*.test.tsx         # L1 + L3
  ai_engine/
    tests/                    # L1
  ingestion/
    tests/                    # L1
  tests_e2e/                  # L4（本 Spec 新增）
    playwright.config.ts
    fixtures/
      users.json
      questions.seed.json     # 种子题库
      paper.golden.json       # 与前端 msw 共享
      llm_scripts/            # LLM mock 脚本
        parse_20_grammar.json
        revise_light.json
        ...
    helpers/
      mockLlm.ts              # e2e 侧的 LLM 替换钩子（通过后端启动参数）
      seedDb.ts               # 通过 CLI 灌入种子题库
    specs/
      auth.spec.ts
      generate.spec.ts
      revise.spec.ts
      submit_and_solutions.spec.ts
      remediation.spec.ts
      mastery.spec.ts
  shared_fixtures/            # A/B/C/D/E 都可引用
    paper.golden.json
    questions.seed.json
```

### 2.2 共享 fixture 命名与来源

| Fixture | 来源 | 消费方 |
|---------|------|--------|
| `questions.seed.json` | 从真实题库导出的一份小规模子集（≤ 50 题，覆盖三种一级题型 + 主要知识点） | L2 集成、L4 e2e |
| `paper.golden.json` | 一份人工审核过的合法 `Paper` JSON | L3 msw、L4 断言、Spec B 回归 |
| `llm_scripts/*.json` | 见 § 3 | L2 monkeypatch、L4 mock server |

**不变量**：所有 fixture 的 schema **必须**通过 Spec A § 2 / Spec C § 2 定义的 pydantic 类型 `.model_validate()` 校验；CI 里有一个 `test_fixtures_schema.py` 显式跑一遍。覆盖范围：
- `paper.golden.json` → `Paper`
- `questions.seed.json` 中的每条 → `Question`
- `llm_scripts/*.json` 中的 `response` → 按 `kind` 分派到 `ParserLLMResponse` / `RevisedQuestion` / `str`（Spec E § 3.5）

**重要**：`llm_scripts` 是本 spec 引入的**最容易漂移**的一类 fixture——AI Engine 内部响应模型是私有协议，schema 变更没有编译期约束通到脚本上。`test_fixtures_schema.py` 是唯一的机器化门禁。

### 2.3 数据库种子
- 每次 e2e 启动前用一个 `seed.py` CLI：
  1. 删除 `test.db`（如果存在）。
  2. 建表（复用后端启动时的建表逻辑）。
  3. 灌入 `questions.seed.json` 到 SQLite + Chroma。
  4. 灌入 `users.json` 里的固定测试账号（`e2e_user` / `password123`，已 bcrypt 好）。
- Chroma 用一个独立的 `test_chroma/` 目录；每次删掉重建。
- Embedding：CI 与 L2/L4 默认用 `shared/embedding_fake.py`（Spec A § 7.1 提供的确定性伪向量）——理由：
  - Qwen 4B 需要 ≥ 4GB 内存并首次加载耗时（GitHub Actions runner 无 GPU、7GB RAM，接近上限）
  - e2e 只走通链路，不做检索质量断言；伪向量 + 属性硬过滤已足够让候选池非空
  - 通过 `EMBEDDING_MODE=fake` 环境变量切换，本地开发者若要用真 Qwen 4B 观察检索质量，覆写为 `real` 即可
- **例外**：`live-smoke`（§ 6.4）用真 Qwen 4B + 真 DeepSeek，跑在有 GPU 的本地机器或专用 nightly runner 上。

---

## 3. LLM Mock 策略

### 3.1 目标
在 L2/L4 中，让 AI Engine 内部的 `shared.llm.deepseek.get_client()` 返回一个**脚本化 client**，行为可预测。

### 3.2 脚本化 client 接口
```python
# tests_e2e/helpers/mock_llm.py（Python 侧，L2 与 L4 共用）
class ScriptedDeepSeekClient:
    """
    与 OpenAI SDK 的 client 结构一致（有 .chat.completions.create），
    以便作为 shared.llm.deepseek.get_client() 的 drop-in 替换。
    按调用顺序 pop 出下一条脚本，脚本类型：parse | revise | solution。
    """
    def __init__(self, scripts: list[Script]):
        self.chat = _Chat(self)  # 暴露 .chat.completions.create

class _Chat:
    def __init__(self, parent): self.completions = _Completions(parent)

class _Completions:
    def __init__(self, parent): self._parent = parent
    def create(self, *, messages, response_model, **kwargs):
        script = self._parent._pop_next()
        # 弱断言 expect_contains；按 script.kind 反序列化到 response_model
        return response_model.model_validate(script.response)
```
- 说明：AI Engine 通过 `instructor` 包装 OpenAI SDK，实际调用形如 `client.chat.completions.create(response_model=...)`。Mock 必须模拟这个嵌套属性链条，否则调用点会 `AttributeError`。
- **弱断言**：脚本可选包含 `expect_contains: [str]`，若 messages 里没出现全部片段则抛 `AssertionError` 并附上 diff。默认不断言（脚本只顺序返回）。
- **顺序敏感**：脚本按 `scripts` 列表顺序被消费；数量不足抛错，数量剩余在 teardown 时抛错（防止漏跑用例）。
- **响应类型**：因为 AI Engine 用 `instructor` 强制 `response_model`（pydantic 类），mock client 直接返回该类的实例，跳过真 JSON 解析。

### 3.3 L2 注入方式
用 `pytest` 的 `monkeypatch`（Spec C § 12 已确认）：
```python
@pytest.fixture
def scripted_llm(monkeypatch):
    client = ScriptedDeepSeekClient([...])
    monkeypatch.setattr("shared.llm.deepseek.get_client", lambda: client)
    yield client
    client.assert_all_consumed()
```

### 3.4 L4 注入方式
Playwright 测试**不能**直接 monkeypatch 后端 Python 进程。改用启动参数：
- 后端有一个环境变量 `LLM_CLIENT_MODE=scripted`，读到就用 `ScriptedDeepSeekClient`（从 `LLM_SCRIPT_FILE` 路径加载脚本）。
- e2e helper 在 `beforeEach` 里：
  1. 写脚本到临时文件。
  2. 通过一个**测试专用管理端点** `POST /api/test/llm-scripts`（仅当 `LLM_CLIENT_MODE=scripted` 时注册）重置脚本队列。
- **安全**：`/api/test/*` 路由只在 `LLM_CLIENT_MODE=scripted` 分支挂载，生产构建永不暴露。

### 3.5 脚本文件结构
```json
{
  "name": "parse_20_grammar",
  "kind": "parse",
  "expect_contains": ["被动语态", "选择"],
  "response": {
    "reasoning": "用户要出被动语态选择题，20 道，无明确改题倾向 → light",
    "knowledge_points": ["kp_single_choice_voice_passive"],
    "knowledge_points_exclude": [],
    "question_types": ["single_choice"],
    "difficulty": [],
    "total_questions": 20,
    "type_distribution": {},
    "difficulty_distribution": {},
    "per_kp_min": 0,
    "revision_intensity": "light"
  }
}
```
- `kind` 与 AI Engine 内部使用的 pydantic 响应类型一一对应：
  - `parse` → `ai_engine.parser.ParserLLMResponse`（Spec B § 3.5）
  - `revise` → `shared.schemas.RevisedQuestion`（Spec A § 2.3）
  - `solution` → 纯字符串（Spec B § 6 Solutioner 用 `client.text()`，非 pydantic 结构；`response` 直接是 `str`）
- Mock client 根据 `kind` 反序列化到对应类型：`parse` / `revise` 走 `model_validate()`；`solution` 直接返回字符串。
- **schema 一致性由 § 2.2 的 `test_fixtures_schema.py` 保证**：脚本 `response` 字段必须能被对应 pydantic 类校验通过。

---

## 4. L4 端到端测试用例

### 4.1 用例清单

| ID | 场景 | 覆盖路径 |
|----|------|---------|
| E1 | 未登录访问 `/` → 跳转 `/login` | Spec D § 3.2 守卫 |
| E2 | 注册 → 登录 → 进入主页 | Spec C /auth/*、Spec D 登录页 |
| E3 | 生成新试卷（20 题、语法主题） | Spec C /papers/generate → AI Engine 全链路 |
| E4 | 重出（revise）：修改意图 = "换成八年级词汇题" | Spec C /papers/{id}/revise |
| E5 | 做题 → 提交 → 展示成绩 | Spec C /attempts、grading 逻辑 |
| E6 | 提交后点解析按钮 → 展示解析 | Spec C /solutions |
| E7 | 提交后 → 错题巩固 → 生成 remediation 试卷 | Spec C /papers/generate mode=remediation |
| E8 | 打开掌握度页 → 树渲染 → 颜色映射正确 | Spec C /users/me/mastery、Spec D MasteryTree |
| E9 | 401 场景：手动清 cookie → 刷新主页 → 跳登录 | Spec D § 6.4 |
| E10 | 429 场景：脚本让后端返回 rate.exceeded → 前端 toast | Spec C 错误码 + Spec D 错误分派 |

### 4.2 用例约定
- 每个用例独立：`beforeEach` 重置 DB + 重置 LLM 脚本。
- 使用固定测试账号 `e2e_user`（除 E2 使用动态注册的账号）。
- 断言方式：优先用 `getByRole` + 可见文本；避免 CSS 选择器。
- 每个用例 ≤ 30 秒；超过说明设计有问题。

### 4.3 关键断言点（示例：E3）
1. 提交生成表单后，主页 **loading skeleton** 出现。
2. 后端返回后，试卷区渲染 **20 张 QuestionCard**。
3. metadata 条显示 `20 题`。
4. 每题题干与 `paper.golden.json` 的对应题一致（可只断言前 3 题避免脆弱）。
5. 数据库中 `papers` 表新增一行，`user_id = e2e_user.id`，`submitted = 0`。

### 4.4 数据库断言方式
- 通过测试专用端点 `GET /api/test/db-inspect?table=papers`（同 § 3.4 的安全约束）。
- **不**直接读 `test.db` 文件：后端进程持续写入该 SQLite 文件，直读虽可行但存在锁竞争与观测时机不一致的风险；统一走 HTTP 更稳定，也与 § 3.4 的测试端点机制一致。

---

## 5. 工具与运行方式

### 5.1 工具栈
| 用途 | 选型 |
|------|------|
| L4 浏览器驱动 | Playwright（chromium only） |
| L4 测试语言 | TypeScript |
| 后端启动 | `uvicorn backend.main:app --port 8001 --env-file .env.e2e`（模块路径对齐 Spec C § 1.3） |
| 前端构建 | `vite build` → 后端 StaticFiles 提供（部署形态 C） |
| 并发 | Playwright `workers: 1`（避免同一 DB 冲突） |

### 5.2 本地跑 e2e
```bash
# 一次性
cd frontend && npm install && cd ..
pip install -r requirements.txt

# 每次
python tests_e2e/helpers/seed.py --db test.db
(cd frontend && npm run build)
LLM_CLIENT_MODE=scripted LLM_SCRIPT_FILE=/tmp/e2e_scripts.json \
  DATABASE_URL=sqlite:///test.db \
  BACKEND_ENV=test \
  uvicorn backend.main:app --port 8001 &
(cd tests_e2e && npx playwright test)
```
封装在一个 `scripts/e2e.sh` 里（Windows 下同名 `.ps1` 版本）。

### 5.3 端口约定
- 生产 / L2：8000
- L4 e2e：8001
- 避免与开发同时跑时冲突。

---

## 6. CI 流水线

### 6.1 分层运行策略
| 事件 | 触发的层 |
|------|---------|
| 每次 push / PR | L1 + L2 + L3 |
| PR 打 `run-e2e` 标签 或 merge to main | L1 + L2 + L3 + L4 |
| 每晚定时（cron） | L1 + L2 + L3 + L4 + **live-smoke**（§ 6.4） |

### 6.2 并行度
- L1 / L2 / L3 三类可完全并行（不同 job）。
- L4 串行跑；单个 job，Playwright workers=1。

### 6.3 失败处理
- L1/L2/L3 失败 → PR 阻塞。
- L4 失败 → PR 阻塞（覆盖**前后端 HTTP 契约 + UI 流程**；LLM 一侧仍是 mock）。
- live-smoke 失败 → **不阻塞** PR，但发通知到指定渠道，人工看是否 LLM 侧变了。

### 6.4 live-smoke（人工触发 / nightly）
- 用真 DeepSeek API。
- 只跑 **E3（生成一份 20 题的试卷）** 一个用例。
- 断言宽松：只断言"返回了合法 `Paper`，题目数量在 15-25 之间"，不断言具体题目。
- 目的：**尽早发现 DeepSeek 契约漂移**（例如 JSON Mode 行为变化）。

---

## 7. 与各 Spec 的测试职责矩阵

| 关注点 | Spec A | Spec B | Spec C | Spec D | Spec E |
|-------|--------|--------|--------|--------|--------|
| 题库摄入单元 | ✅ | | | | |
| EPUB→md、章节切分、KP 抽取 | ✅ | | | | |
| AI Engine 模块单元（parser/retriever/reviser/solutioner/analyzer） | | ✅ | | | |
| AI Engine golden set 回归（真 LLM，离线） | | ✅ | | | |
| FastAPI 端点集成 | | | ✅ | | |
| 鉴权 / Session / 权限 | | | ✅ | | |
| 前端组件 | | | | ✅ | |
| 前端路由守卫 | | | | ✅ | |
| e2e 全链路（mock LLM） | | | | | ✅ |
| LLM 契约漂移探测（live-smoke） | | | | | ✅ |
| 共享 fixture 定义 | | | | | ✅ |

---

## 8. 非目标（本 Spec 不做）

1. 性能 / 负载测试（无高并发需求）。
2. 视觉回归（Percy / Chromatic）。
3. 无障碍自动化（axe-core）。
4. 跨浏览器测试（只测 chromium）。
5. 移动端 e2e（Spec D § 10 已声明不支持）。
6. 混沌工程 / fault injection（AI Engine 内部的重试逻辑已在 Spec B 单元层覆盖）。

---

## 9. 开放问题

1. **e2e 稳定性**：Playwright + StaticFiles 首次加载慢导致 flaky 时，是否引入等待 hook？→ 观察 CI 前 2 周表现再定。
2. **测试账号 bcrypt cost**：为加快 seed 是否降低测试环境 bcrypt cost（如 4）？→ 默认降到 4，仅测试环境（Spec C 生产用 12）。
3. **共享 fixture 的版本化**：schema 变更时如何避免 fixture 静默失效？→ § 2.2 的 `test_fixtures_schema.py` 覆盖。

---

## 10. 里程碑 M7（跨系统测试落地）

**M7 完成标准**：
1. `tests_e2e/` 目录搭好，10 个用例（E1-E10）全部通过。
2. `ScriptedDeepSeekClient` + 脚本文件 loader 就绪，被 L2 与 L4 同时使用。
3. CI 配置好三种触发时机（§ 6.1）。
4. `test_fixtures_schema.py` 覆盖所有共享 fixture。
5. 手动能跑一次 live-smoke 通过（真 DeepSeek）。

依赖：M5（后端 MVP）+ M6（前端 MVP）已完成。

---

## 11. 不变量（Invariants）

跨系统测试必须始终保证：

1. **e2e 永远 mock LLM**：CI 主流程不打真 LLM，除 live-smoke 例外。
2. **测试用管理端点不进入生产**：`/api/test/*` 只在 `LLM_CLIENT_MODE=scripted` 分支挂载。
3. **fixture schema 与 pydantic 类型对齐**：任何 fixture 变更必须通过 `test_fixtures_schema.py`。
4. **e2e 独立**：每个用例 `beforeEach` 重置 DB + LLM 脚本；用例之间无隐式依赖。
5. **单一职责**：单元 / 集成 / 组件 / e2e 各司其职，禁止在 e2e 里做 "顺便测个 SQL 逻辑" 这类越层测试。
6. **live-smoke 不阻塞 PR**：LLM 侧异常不应阻塞代码合入，只应发通知。

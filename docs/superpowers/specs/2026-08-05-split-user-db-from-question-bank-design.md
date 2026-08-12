# 设计：用户库与题库分离（A 方案）

日期：2026-08-05
状态：已批准设计，待写实现计划
分支：`debug`

## 背景与问题

后端默认 `db_path = data/questions.db`（`shared/config.py:32`）。**用户数据和题库共用同一个被 git 跟踪的 SQLite 文件**：

| 表 | 归属 | 现状行数 |
|---|---|---|
| `questions` / `knowledge_points` / `question_knowledge_points` | 题库（应跟踪） | 1397 / 49 / … |
| `users` / `sessions` / `papers` / `attempts` / `attempt_items` / `study_plans` | 用户数据（不应跟踪） | 4 / 4 / 10 / 10 / 47 / … |

`.gitignore` 排除了 `data/payment.db`、`data/agent_sessions.db*`，**唯独没排 `data/questions.db`**，而它恰恰混装了用户数据（含密码哈希）。

由此产生两类风险：

1. **`git pull` 覆盖/冲突**：远程更新过 `questions.db` 时，`pull` 会用远程版本覆盖本地，丢失本机用户与答题数据；且本地文件常处于 `M`（脏）状态，二进制 SQLite 无法三方合并，`pull` 易失败或卡合并。
2. **历史泄露**：仓库已提交的 `questions.db` 内含 4 个用户的密码哈希，任何 clone 都能读到。

根因症状：集成测试 `test_backend_flow_against_copied_real_question_bank` 里的 `assert attempt_count == 1` 已失败（实际 10 行）——正是真实用户答题数据积压在被跟踪的题库文件里。

## 关键架构事实（决定选型）

排查全部 SQL 后确认：**没有任何查询把用户表和题库表 JOIN 在同一条语句里**。`attempt_items.source_question_id` 和 `kps_json` 只是以纯 TEXT/JSON 形式引用题库实体，无 SQL 外键、无跨组 JOIN（所有 JOIN 都在组内）。

因此可以干净地拆成两个物理文件，**无需 `ATTACH DATABASE` 或跨库查询**。唯一的工作是把每个消费方路由到正确的文件。

## 选型

- **A1 —— 两个文件 + 两个连接函数（采纳）**：`connect()` → 用户/app 库；新增 `connect_bank()` → 题库。因无跨组 JOIN，这是最简单且正确的拆法。
- **A2 —— 两个文件 + `ATTACH DATABASE`（否决）**：能让现有单连接代码不改就跑，但既然没有跨库查询需求，纯属多余复杂度。

## 目标状态

### 两个文件

| 文件 | git 跟踪 | 表 |
|---|---|---|
| `data/questions.db` | ✅ 是（只读题库） | `questions`、`knowledge_points`、`question_knowledge_points` |
| `data/app.db` | ❌ gitignore（`data/app.db*`） | `users`、`sessions`、`papers`、`attempts`、`attempt_items`、`study_plans`、`schema_migrations` |

`schema_migrations` 归**用户库**：代码中每一条 migration（`_migrate_users_role` / `_migrate_users_status` / `_migrate_attempt_items_*`）改的都是用户表；题库由离线 ingestion 构建，不走 migration 机制。

### 配置（`shared/config.py`）

- 保留 `db_path: Path = Path("data/questions.db")`，语义收窄为**题库**；环境变量仍是 `SQLITE_PATH`。
- 新增 `app_db_path: Path = Path("data/app.db")`，语义为**用户/app 库**；环境变量 `APP_DB_PATH`。
- `get_config()` 里为 `app_db_path` 加上和 `db_path` 同样的 env 覆盖逻辑。

### 存储层路由（`shared/storage.py`）

现有单一 `connect()` 拆为两套：

- **用户库（app）**：`connect()` / `get_db_path()` / `set_db_path()` 改为指向 `config.app_db_path`。`init_db()` 只建用户表（含 `schema_migrations` + migrations）。绝大多数 storage 函数属此类。
- **题库（bank）**：新增 `connect_bank()` / `get_bank_db_path()` / `set_bank_db_path()`，指向 `config.db_path`。**只读**，不建表、不跑 migration。

`storage.py` 中改用 `connect_bank()` 的题库函数（共 5 处，排查确认无遗漏）：
`list_knowledge_points`、`get_question`、`list_questions`、`write_question_solution`，以及它们调用的 helper `_row_to_question`。这些函数去掉对 `init_db()` 的调用（题库不需要建表）。其余函数保持 `connect()`（用户库）。

### AI 引擎与 agent

- `ai_engine/parser.py`、`solutioner.py`、`question_repo.py`、`ingestion/`：本就用 `cfg.db_path` / 显式路径读题库 —— **不动**（`db_path` 语义未变，仍是题库）。
- `ai_engine/analyzer.py`：`_db_path()` 返回 `storage.get_db_path()`，读的是 `attempts`/`attempt_items`（用户表）。因 `get_db_path()` 现指向 app 库，**自动正确**，无需改动。
- `agent/tools.py`：
  - `get_user_history`（读 `attempts`/`attempt_items` 用户表 + `knowledge_points` 题库表）：需分别用 app 连接和 bank 连接。`_connect()` 拆为 `_connect_app()` / `_connect_bank()`（或直接用 `storage.connect()` / `storage.connect_bank()`）。
  - `get_example_questions`（读 `questions`/`question_knowledge_points` 题库表）：改用 bank 连接。

### 就绪检查（`backend/api/health.py`）

`_readiness_checks()` 开**两个**连接：

- app 库：`sqlite`、`core_tables`（`users`/`sessions`/`papers`/`attempts`/`attempt_items`/`schema_migrations`）。
- bank 库：`question_bank`、`vector_bank`（后者已在前序改动中收敛到 `VECTOR_INDEXED_QUESTION_TYPES`）。

`_has_question_bank` / `_has_vector_bank` 接收 bank 连接；`core_tables` 检查接收 app 连接。

### 仓库清理

1. 从被跟踪的 `data/questions.db` 中 `DROP TABLE` 掉 6 张用户表 + `schema_migrations`，`VACUUM` 压实。
2. `git add data/questions.db` 提交这份「已剥离用户表」的干净题库。
3. `.gitignore` 增加 `data/app.db*`。
4. 现有 4 个 dev 用户/试卷**丢弃**（用户选择「从零开始」）；首次运行 `init_db()` 会新建空 `app.db`。

### 测试

- `tests/integration/backend/conftest.py` 的 `client` fixture：拆分后 `storage.set_db_path()` 指向 **app 库**，故 `set_db_path(tmp/app.db)` + `setenv APP_DB_PATH=tmp/app.db` 即可。这些测试用 mock 的 AI gateway，不读真实题库，bank 路径无需设置（保持默认；用例不触题库函数）。原先 `setenv SQLITE_PATH` 改为 `setenv APP_DB_PATH`。
- `test_health.py::test_readiness_reports_missing_question_bank`：app 库存在（`sqlite`/`core_tables` = True），题库缺失（`question_bank`/`vector_bank` = False）—— 需分别设置两个路径。
- `test_real_database_schema.py` 与 `test_health.py::test_readiness_accepts_real_question_bank_copy`：**bank** 指向拷贝的真实 `questions.db`，**app** 指向临时文件让 `init_db()` 现建用户表。这同时修复既有的 `attempt_count == 1` 失败（全新 app.db → 0 条 attempt，断言应相应调整为 0 或按新建流程校验）。
- `test_rate_limit.py`：同 conftest，改指 app 路径。

## 数据流（分离后）

```
读题库（只读）:  parser/solutioner/question_repo/ingestion ─┐
                storage.get_question/list_questions/…      ├─→ connect_bank() → data/questions.db
                agent.get_example_questions                 ┘
读写用户数据:    storage.create_user/save_paper/write_attempt/… ─┐
                analyzer.build_profile                          ├─→ connect() → data/app.db
                agent.get_user_history（用户部分）              ┘
```

## 影响清单（文件级）

- `shared/config.py` — 加 `app_db_path` + env 覆盖。
- `shared/storage.py` — 拆连接函数；5 个题库函数改 `connect_bank()`；`init_db()` 只建用户表。
- `backend/api/health.py` — 就绪检查开两连接。
- `agent/tools.py` — `_connect` 拆分，两个工具各走对应库。
- `.gitignore` — 加 `data/app.db*`。
- `data/questions.db` — 剥离用户表并重新提交。
- 测试：`conftest.py`、`test_health.py`、`test_real_database_schema.py`、`test_rate_limit.py`。
- 文档：`docs/backend-design.md`（若描述了单库假设，同步更新）；`CLAUDE.md`（数据契约段落补一句「用户库 `app.db` 与题库 `questions.db` 物理分离」）。

## 验证

- `PYTHONIOENCODING=utf-8 python -m pytest tests/ -v` 全绿（含此前失败的 `attempt_count`）。
- `BACKEND_ENV=production ... python -m backend.cli deploy-check` → `status: ready`。
- `git ls-files data/` 不含 `app.db`；`data/questions.db` 内已无用户表。
- 手动冒烟：删除本地 `data/app.db`，`init_db()` 能新建；注册用户→生成试卷→答题→判分全链路通。

## 非目标（YAGNI）

- 不做现有 4 个 dev 用户的数据迁移（用户已选「从零开始」）。
- 不做 git 历史重写（旧 blob 中的密码哈希仍在历史里；如需彻底清除是另一独立任务）。
- 不引入 ORM 或多租户分库。

# 思维导图功能设计（学习助手 · Mind Map）

- 日期：2026-08-13
- 状态：设计已与用户确认，待评审
- 关联规格：`agent-design.md`、`frontend-design.md`、`backend-design.md`

## 1. 目标与范围

给中考英语学习助手（Coach agent）增加**思维导图**能力，作为学生整理语法/知识点讲解的可视化工具与创作工作区。

**本次做（In scope）**

1. **A 类导图 = 语法/知识点讲解导图**：把一个知识点（如"现在完成时"）拆成结构 / 用法 / 标志词 / 易错点等分支，画成思维导图辅助记忆。
2. Coach agent 在聊天中生成导图（工具持久化 + 标记通道）。
3. 左侧栏新增 **「思维导图」** 页（在「复盘」分组内）：列表 + 新建 + 查看 + 重命名 + 删除。
4. 思维导图**详情/编辑页**：大纲编辑器 + Markmap 实时预览 + **右侧可调出的内嵌助手**（复用学习助手），支持**对话式改图**。
5. 生成/新建的导图**自动保存**；编辑（手动或对话）**自动保存、直接覆盖**。

**本次不做（Out of scope）**

- B 类「学情/薄弱点导图」：后续由前端在学情报告里 hardcode 可视化，不走 LLM，本设计不覆盖。
- 静态图片（PNG/SVG 文件）导出与服务端渲染：纯前端渲染，不生成图片文件。
- 手动拖拽节点摆位置（Markmap 自动布局；"编辑"= 改大纲文本）。

## 2. 核心原则

**大纲 markdown 是唯一事实来源（single source of truth）。** 每张导图在库中只存一份层级大纲 markdown；聊天缩略、详情页预览、对话式改图，全部是"取大纲 → Markmap 实时渲染"。"编辑"永远等价于"改大纲 → 覆盖保存"。

这与现有 `generate_paper` → `<paper_ready>` → `action:open_paper` 通道完全同构，不引入新的消息多模态类型。

**大纲格式**：标准 markdown 嵌套列表（Markmap 原生格式）：

```markdown
# 现在完成时
## 结构
- have/has + 过去分词
## 用法
- 表经历
- 表持续到现在
## 标志词
- already / yet / ever
## 易错点
- vs 一般过去时
```

## 3. 数据流

### 3.1 聊天中生成（全局学习助手）

```
学生: "用思维导图讲讲现在完成时"
 → Coach 命中 mindmap skill
 → 调 create_mindmap(topic, outline_markdown)
      · storage.save_mindmap(user_id, topic, outline_md) → 返回 mindmap_id
 → agent 回复末尾留 <mindmap_ready mindmap_id="xxx"/>
 → 后端 _parse_action() → action={type:"open_mindmap", mindmap_id, title}
 → 前端聊天气泡下渲染 <MindmapView>（只读缩略）+ 点击 → 跳 /mindmaps/{id}
 → 该图已自动出现在「思维导图」页
```

### 3.2 详情页对话式改图（内嵌助手）

```
用户在 /mindmaps/{id} 右侧助手面板输入: "把'易错点'再展开两条"
 → AssistantChat 发送 { message, scope:"mindmap", mindmap_id, session_token }
 → 后端: 选 session_id="user_{uid}_mm_{token}" + 绑定 mindmap_id 到 ContextVar
 → Coach 命中 mindmap skill（有 mindmap_id 分支）
      · get_current_mindmap() 读现状 → 生成新大纲 → update_current_mindmap(new_md) 覆盖保存
 → agent 回复末尾留 <mindmap_updated/>
 → 后端 _parse_action() → action={type:"mindmap_updated", mindmap_id}
 → 前端详情页 invalidate ['mindmap', id] → 编辑器 + 预览自动刷新
```

## 4. 后端设计（Python）

### 4.1 数据表（`data/app.db`，gitignored）

镜像 `study_plans`（`shared/storage.py:169`）。加入 `init_db()` 建表块（`storage.py:114`）：

```sql
CREATE TABLE IF NOT EXISTS mindmaps (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    title TEXT NOT NULL,             -- 默认取 topic / 根节点，可重命名
    knowledge_point TEXT,            -- 可选，关联知识点名（纯展示）
    outline_md TEXT NOT NULL         -- 大纲 markdown = 事实来源
);
CREATE INDEX IF NOT EXISTS idx_mindmaps_user ON mindmaps(user_id, created_at);
```

**迁移**：新增 `MIGRATION_MINDMAPS = "20260813_001_mindmaps"` + `_migrate_mindmaps()`（`CREATE TABLE IF NOT EXISTS` + 索引），注册进迁移列表（`storage.py:1228-1235`）。保证已有 app.db 平滑升级。

### 4.2 storage CRUD

镜像 `save_study_plan` / `list_papers`（全部 `WHERE user_id=?`）：

- `save_mindmap(user_id, title, outline_md, knowledge_point="") -> str`（返回 id）
- `get_mindmap(user_id, mindmap_id) -> dict | None`
- `list_mindmaps(user_id, limit=20, offset=0) -> list[dict]`
- `update_mindmap(user_id, mindmap_id, *, outline_md=None, title=None) -> bool`（覆盖，刷新 updated_at）
- `delete_mindmap(user_id, mindmap_id) -> bool`

### 4.3 Agent 工具（`agent/tools.py`）

镜像 `generate_paper`（`tools.py:347`）；user_id 与 mindmap_id 均从 ContextVar 取，**不做 LLM 入参**（沿用现有 `_current_user_id` 安全机制，新增 `_current_mindmap_id`）。

```python
@function_tool
def create_mindmap(topic: str, outline_markdown: str) -> str:
    """把一个语法/知识点讲解整理成思维导图并保存。返回 {mindmap_id, title}。"""
    # 校验 outline 至少含一个 '#' 根节点，否则返回 error；save 失败显式返回 error

@function_tool
def get_current_mindmap() -> str:
    """读取当前正在编辑的思维导图大纲（编辑页上下文）。返回 {mindmap_id, title, outline_markdown}。"""

@function_tool
def update_current_mindmap(outline_markdown: str) -> str:
    """覆盖保存当前正在编辑的思维导图。返回 {ok, mindmap_id}。"""
```

注册进 `coach.py:140` tools 列表 + `coach.py:22` import。

### 4.4 Skill（`agent/skills/mindmap.md`）

镜像 `generate_paper.md`。要点：

- **触发词**："画/整理成思维导图""用导图讲讲…""脑图整理"。
- **边界**：要做题 → `generate_paper`；要导图 → 本 skill。明确区分，避免混淆。
- **两种上下文**：
  - 无当前图（全局聊天）：自己组织层级大纲 → `create_mindmap` → 末尾留 `<mindmap_ready mindmap_id="…"/>`。
  - 有当前图（编辑页）：先 `get_current_mindmap` 读现状 → 按用户要求改 → `update_current_mindmap` → 末尾留 `<mindmap_updated/>`。
- 不解释标记，标记后不加任何文字。

> 注意：`_load_skills()` 按文件名排序拼接（`coach.py:112`），新文件排在中间对 prompt 无害。

### 4.5 路由与 marker 解析（`backend/api/agent.py`）

**Schema 扩展**（`backend/schemas.py:143` + 镜像 `shared/schemas.py`）：

```python
class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    scope: Literal["global", "mindmap"] = "global"   # 新增，默认不破坏现有
    mindmap_id: str | None = None                     # scope=mindmap 时必填
    session_token: str | None = None                  # 编辑页用，隔离临时会话
```

**`_parse_action()`**（`agent.py:19-23`）新增两条正则：
- `<mindmap_ready mindmap_id="X"/>` → `{"type":"open_mindmap","mindmap_id":X}`
- `<mindmap_updated/>` → `{"type":"mindmap_updated","mindmap_id": <当前绑定 id>}`

**`agent_chat`**（`agent.py:32`）改动：
- 依 `scope` 选 session：global → `user_{uid}`（不变）；mindmap → `user_{uid}_mm_{session_token}`（新会话，每次前端挂载生成新 token → 满足"每次打开都是新对话"）。
- `scope=="mindmap"` 时 `set_current_mindmap_id(body.mindmap_id)`（先校验该图属于该 user，404 则拒绝）。

**新路由**（镜像 `study-plans/latest:103`，均 `Depends(current_user)`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/agent/mindmaps` | 分页列表（镜像 `list_papers`） |
| GET | `/agent/mindmaps/{id}` | 取单张（含 outline_md） |
| POST | `/agent/mindmaps` | 手动新建（空图或带初始大纲）→ 返回 id |
| PATCH | `/agent/mindmaps/{id}` | 覆盖保存 outline_md / title（自动保存 & 重命名都走这里） |
| DELETE | `/agent/mindmaps/{id}` | 删除 |

## 5. 前端设计（React + Vite）

### 5.1 依赖

新增 `markmap-lib`（markdown → 数据）+ `markmap-view`（数据 → SVG）。纯前端，无系统级依赖。

### 5.2 共用组件（`frontend/src/components/mindmap/`）

- `<MindmapView outline={md} interactive?/>` — Markmap 挂到 `<svg>` ref，只读渲染，支持缩放/折叠。聊天缩略 + 详情预览共用。
- `<MindmapEditor outline onChange />` — 左/上 `<textarea>` 大纲，右/下 `<MindmapView>` 实时预览。**自动保存**：大纲变更 debounce（~600ms）后调 PATCH。

### 5.3 内嵌助手组件抽取

把 `AssistantPage` 的聊天逻辑抽成 `<AssistantChat scope storageKey mindmapId? sessionToken? onAction? />`：

- `AssistantPage`：`scope="global"`、`storageKey="agent.chat"`（行为原样不变）。
- 详情页面板：`scope="mindmap"`、`mindmapId`、每次挂载生成 `sessionToken`、`storageKey` 含 token（不跨会话复用）；`onAction` 收到 `mindmap_updated` → invalidate `['mindmap', id]`。
- `stripInternalTags`（`AssistantPage.tsx:28`）扩展：额外滤掉 `<mindmap_ready…/>`、`<mindmap_updated/>`。
- `ChatMessage.action` / `AgentAction`（`types/api.ts`）扩展 `open_mindmap`、`mindmap_updated`。

### 5.4 聊天界面接入（`AssistantPage.tsx`）

在 `open_paper` 分支（`:189`）旁加 `open_mindmap` 分支：渲染 `<MindmapView>` 只读缩略 + 点击整块跳 `/mindmaps/{id}`（不再内嵌编辑器）。

### 5.5 新页面

- `MindmapsPage.tsx`（`/mindmaps`）：镜像 `PapersPage`，`useInfiniteQuery(['mindmaps','list'])`，行式列表（日期/标题/知识点）+ 行内「重命名」「删除」+ 顶部「＋ 新建思维导图」（POST 空图 → 跳详情）。空态引导去学习助手或新建。
- `MindmapDetailPage.tsx`（`/mindmaps/:id`）：三栏工作区 = 大纲编辑器（含实时预览）+ 右侧可折叠 `<AssistantChat scope="mindmap">`。

### 5.6 路由 / 路径 / 侧栏

- `paths.ts`：`mindmaps: '/mindmaps'`、`mindmap: (id) => '/mindmaps/' + id`。
- `routes.tsx`：两条 `<RedirectIfAdmin>` 路由（`:59` 附近）。
- `nav.ts`：**「复盘」组**内（历史试卷后）加一项，label「思维导图」，icon 用 lucide `Network`（或 `GitBranch`）。
- `api/agent.ts`：新增 `listMindmaps` / `getMindmap` / `createMindmap` / `updateMindmap` / `deleteMindmap`；`agentChat` 支持传 scope/mindmap_id/session_token。

## 6. 边界与错误处理

- **保存失败**：`create_mindmap` / `update_current_mindmap` 存库失败必须显式返回 error（不给前端打不开的 id）——沿用 `generate_paper` 的做法。
- **大纲非法**：工具侧最小校验（至少一个 `#` 根节点），否则返回 error 让 agent 重试。
- **聊天缓存**：`sessionStorage` 只存 action 的 id/title，不存大纲全文；大纲永远按 id 现取现渲染，避免膨胀。
- **删除后引用**：旧聊天气泡点「查看」若图已删 → 404 → toast「该思维导图已删除」。
- **权限/隔离**：所有路由 `Depends(current_user)`；storage 全部 `WHERE user_id=?`；工具的 user_id/mindmap_id 服务端绑定，不信任 LLM 入参。
- **自动保存并发**：手动编辑 debounce PATCH 与对话式改图都走"覆盖"语义；对话改图后前端 invalidate 拉最新，编辑器以服务端返回为准（后写覆盖先写，可接受）。

## 7. 工作量预估

| 部分 | 量 |
|------|-----|
| 后端：表+迁移+CRUD+3 工具+skill+schema+5 路由+marker | ~1 天 |
| 前端：MindmapView/Editor + Markmap 接入 | ~1 天 |
| 前端：AssistantChat 抽取 + 详情页三栏 + 对话改图联动 | ~1 天 |
| 前端：列表页 + 路由/路径/侧栏 + api | ~0.5 天 |
| 联调 + 边界 | ~0.5 天 |
| **合计** | **~4 天** |

## 8. 关键文件清单（接入点）

- `shared/storage.py` — `init_db()`(:114 建表)、迁移列表(:1228)、新 CRUD（镜像 `save_study_plan`:1322 / `list_papers`:535）
- `agent/tools.py` — 3 新工具（镜像 `generate_paper`:347）+ `_current_mindmap_id` ContextVar
- `agent/coach.py:22,140` — import + 注册工具
- `agent/skills/mindmap.md` — 新 skill（镜像 `generate_paper.md`）
- `backend/api/agent.py:19-23,32-59` — `_parse_action` 扩展、`agent_chat` scope/session/绑定、5 新路由
- `backend/schemas.py:143` + `shared/schemas.py` — `AgentChatRequest` 加 scope/mindmap_id/session_token
- `frontend/src/components/mindmap/` — `MindmapView`、`MindmapEditor`
- `frontend/src/components/AssistantChat.tsx` — 从 `AssistantPage` 抽取的可复用聊天
- `frontend/src/pages/AssistantPage.tsx` — 改用 `AssistantChat`；`stripInternalTags`、action 分支
- `frontend/src/pages/MindmapsPage.tsx`、`MindmapDetailPage.tsx` — 新页面
- `frontend/src/routes.tsx`、`lib/paths.ts`、`lib/nav.ts`、`api/agent.ts`、`types/api.ts`
- `frontend/package.json` — `markmap-lib`、`markmap-view`

# 远程前端联调：后端部署交接指南

本指南由后端负责人执行。目标是把**前端页面和 API 放在同一个 HTTPS 地址**，使异地队友无需复制 API Key、题库、Chroma 索引或 embedding 模型，也能完成登录与真实 AI 全链路验收。

> 临时演示使用 Cloudflare Quick Tunnel。它的地址会随进程结束失效，不具备生产可用性保证；不要用于正式对外发布。

## 0. 职责边界

- 后端负责人机器：保留 `.env`、API Key、`data/questions.db`、`data/chroma` 与本地 embedding 模型；这些都不得提交 Git。
- 前端负责人：交付可构建的前端产物，且所有 API 请求使用相对路径 `/api` 并携带 `credentials: "include"`。
- 远程队友：只访问后端负责人分享的 HTTPS 地址。

## 1. 准备前端同源产物

前端项目完成后，在项目根目录执行其构建命令（通常是 `npm run build`）。将构建目录**内的内容**复制到本项目的 `backend/static/`：

```powershell
New-Item -ItemType Directory -Force backend/static
Copy-Item <前端构建目录>\* backend/static -Recurse -Force
```

复制完成后必须存在 `backend/static/index.html`。FastAPI 启动时会自动把该目录挂载为网站根路径；页面请求 `/api/*` 仍由后端路由处理，因此 Cookie 与 API 同源。

## 2. 配置真实后端环境

在本机 `.env` 设置（不要提交该文件）：

```env
BACKEND_ENV=production
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
BACKEND_STATIC_DIR=backend/static
SQLITE_PATH=data/questions.db
CHROMA_PATH=data/chroma
LLM_API_KEY=你的真实密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

生产模式会将会话 Cookie 标记为 `Secure` 和 `SameSite=Strict`。因此远程访问必须走 HTTPS；下文的 Cloudflare Tunnel 会提供 HTTPS。

确保真实题库、Chroma 索引和 embedding 模型已经准备完成。运行以下命令检查所有部署前置条件：

```powershell
python -m backend.cli deploy-check
```

只有输出 `"status": "ready"` 时再继续。常见失败项：

- `static_index=false`：前端尚未构建或未复制到 `backend/static/`。
- `question_bank=false` / `vector_bank=false`：没有导入真实题库或 Chroma 索引。
- `llm_api_key=false`：`.env` 中没有有效密钥。
- `production_mode=false`：尚未设置 `BACKEND_ENV=production`。

## 3. 启动与本机验收

```powershell
python -m backend.cli serve --host 127.0.0.1 --port 8000
```

在浏览器打开 `http://127.0.0.1:8000/`，确认前端页面出现；再访问 `http://127.0.0.1:8000/api/health/ready`，确认返回 `ready`。

## 4. 暴露临时 HTTPS 地址

安装 Cloudflare 的 `cloudflared` 后，在**另一个终端**运行：

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

终端会输出一个 `https://*.trycloudflare.com` 地址。将该地址发给队友；后端和隧道进程都必须持续运行。

Quick Tunnel 适合团队短期联调，随机地址、停止即失效，且不提供 SLA。正式部署请使用有固定域名的 Cloudflare Named Tunnel 或云服务器反向代理。

## 5. 验收清单

由异地队友在分享的 HTTPS 地址依次验证：

1. 注册并刷新页面，确认登录状态仍存在。
2. 生成试卷、完成作答并提交。
3. 打开掌握度页面。
4. 请求单题解析。
5. 改卷后确认切换到新的试卷记录。

如果只有 `/api` 被暴露，而前端页面仍运行在队友电脑的 `localhost`，会形成跨站 Cookie 场景，登录态可能被浏览器拦截；这种方式不作为完整联调方案。

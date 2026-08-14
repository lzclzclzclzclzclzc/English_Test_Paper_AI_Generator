# 验收仿真数据

本项目提供完全虚构的验收数据，用于展示多用户的出卷、答题、掌握度与背词使用情况。数据范围为 **2026-07-15 至 2026-09-05**，不使用任何真实个人信息。

## 生成与启动

在仓库根目录运行：

```powershell
python scripts/seed_acceptance_demo.py --reset
$env:APP_DB_PATH = "data/acceptance-demo.db"
python -m backend.cli serve
```

另开一个终端启动前端：

```powershell
cd frontend
npm.cmd run dev
```

生成器会输出：

- `data/acceptance-demo.db`：独立的用户数据，不会覆盖日常使用的 `data/app.db`；
- `data/acceptance-demo-accounts.csv`：全部 38 个验收账号。

所有账号均使用密码 `Demo2026!`。建议优先使用 `admin_zhou` 登录后台，或使用 `liuyt2026`、`chenxr2026`、`wangzy2026` 查看不同活跃度的学习记录。

验证生成结果：

```powershell
python scripts/seed_acceptance_demo.py --verify
```

## 交付老师

将 `data/acceptance-demo.db` 改名或复制为 `data/app.db`，并附上账号 CSV，即可按默认启动方式验收。`data/questions.db` 是版本化题库，必须与当前代码一同交付。

9 月 1–5 日为模拟未来记录；若在 2026-09-05 前验收，部分“今日”或“近 30 天”视图不会计入这些记录。

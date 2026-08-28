# 验收仿真数据

本项目提供完全虚构的验收数据，用于展示管理员监控、出卷、答题、背词、积分、营收与作文批改。数据范围为 **2026-07-15 至 2026-08-31**，不使用任何真实个人信息、AI 服务或支付服务。

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

- `data/acceptance-demo.db`：独立验收数据库，不会覆盖日常使用的 `data/app.db`；
- `data/acceptance-demo-accounts.csv`：1094 个账号（1091 名虚构普通用户、3 名管理员）的登录清单。

所有账号均使用密码 `Demo2026!`。管理员账号为 `admin_zhou`、`admin_li`、`admin_wang`；普通用户账号采用虚构英文名组合，可从账号 CSV 选择。

数据库会构造全部管理员监控所需数据：AI 功能调用与积分消耗、每日积分消耗、TOP10 消耗用户、每日新增/出卷/背词、做题正确率、作文批改、积分账户、订单、每日收入及三种积分套餐收入。所有账号余额均为 0–900 的 10 倍数。

验证生成结果：

```powershell
python scripts/seed_acceptance_demo.py --verify
```

## 队友与老师使用

脚本和说明会提交 Git；生成的数据库与账号 CSV 被 `.gitignore` 排除。队友切换到 `acceptance-demo-data` 分支后执行上述 `--reset` 命令，即可在本地从空库生成同一套验收数据。

若需要直接交付已生成数据，将 `data/acceptance-demo.db` 与账号 CSV 单独打包；复制数据库为 `data/app.db` 后可按默认方式启动，但会覆盖该机器原有的日常本地数据。

# 题库运行数据

真实题库与向量索引是运行数据，不随 Git 分发。这样可以避免提交大体积二进制索引、教材源文件和可能受版权约束的内容，也能避免每次重新建索引产生无意义的 diff。

## 版本控制边界

保留在仓库中的、可审查的题库源数据：

- `data/chapters/*.json`：已人工修补的章节题目记录。
- `data/kb/knowledge_tree.json`：已人工审核的知识点树。

由题库负责人通过受控数据包或共享存储提供、不得提交的运行数据：

- `data/questions.db`：SQLite 题库。
- `data/chroma/`：Chroma 持久化索引。
- `data/books/`：原始 EPUB 教材。
- `data/raw_md/`：EPUB 转换得到的中间 Markdown。
- `data/kb/knowledge_tree_draft.html`：审核过程中的可视化草稿。

## 本地安装

向题库负责人获取与当前 `data/chapters/` 和 `data/kb/knowledge_tree.json` 对应的运行数据包，并解压到项目根目录，使下列路径存在：

```text
data/questions.db
data/chroma/chroma.sqlite3
```

然后按 `.env.example` 设置 `SQLITE_PATH` 与 `CHROMA_PATH`，并运行：

```powershell
python -m backend.cli deploy-check
```

只有检查结果为 `"status": "ready"` 时，真实题库的 API 验收才可进行。

## 测试行为

默认测试始终覆盖临时 SQLite 数据库。安装数据包后，真实题库和 Chroma 兼容性测试也会执行；未安装时，这些测试会显示为 `skipped`，不会把缺失的私有运行数据误报为代码失败。

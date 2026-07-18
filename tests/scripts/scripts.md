# Interactive Scripts

## Pipeline 完整交互脚本（推荐）

运行完整 Parser → Retriever → Reviser pipeline，输入自然语言 prompt，查看生成的试卷。

```bash
PYTHONIOENCODING=utf-8 python tests/scripts/interactive_pipeline.py
```

支持前缀选项：
- `--mode remediation`：错题补练模式
- `--mode review --user <user_id> --days 30`：历史复习模式

示例输入：
```
prompt> 来10道现在完成时的单选题
prompt> --mode remediation 针对我的错题再练几道
prompt> 来5道关于环保的单选题
```

## Pipeline 批量测试 + 报告

运行 10 个预设 prompt，输出 Markdown 报告到 `tests/scripts/pipeline_report_<时间戳>.md`。

```bash
PYTHONIOENCODING=utf-8 python tests/scripts/pipeline_report.py
```

## Parser 模块交互脚本

运行 Parser 模块，输入自然语言指令，查看结构化的 GenerateRequest 输出。

```bash
PYTHONIOENCODING=utf-8 python tests/scripts/interactive_parser.py
```

## Reviser 模块交互脚本

运行 Reviser 模块，输入参数测试题目修订，查看试卷生成结果。

```bash
PYTHONIOENCODING=utf-8 python tests/scripts/interactive_reviser.py
```

## 退出方式

- 输入 `exit` / `quit` / `q`
- 或按 `Ctrl+C`

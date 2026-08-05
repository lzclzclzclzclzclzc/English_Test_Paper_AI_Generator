# 背词词表数据

默认导入文件是 `national-core-plus-shanghai-extension.json`：

- `moe-2022-core-1600.json` 保存教育部《义务教育英语课程标准（2022年版）》附录三级词汇表的可追溯词项清单，含官方发布页、文档镜像、获取日期和 SHA-256；其 1,600 个源词项在合并时按词形去重。
- `shanghai-basic-1678.json` 是既有“上海课程标准依据词表（第三方整理）”。它不是上海市教委直接发布的机器可读官方数据，因此页面必须明确标注为第三方整理。
- `national-core-plus-shanghai-extension.json` 保留已有词 ID，并将同形的国家核心词标为 `national_core`；其余原有词标为 `shanghai_extension`。缺失的核心词补入该文件。

使用 `python -m backend.cli seed-vocabulary` 导入。导入会校验条数、ID、标准化词形、来源元数据和类别，不会删除用户进度、日志或已生成的当日任务。

教育部词表只决定“是否属于国家核心词”。为补齐现有词表没有的短中文释义，`dictcn-short-glosses.json` 保存了导入时使用的辅助字典短释义；它不是词表权威来源。真实例句仍需单独建设和审核，当前演示模板不会在页面中展示。

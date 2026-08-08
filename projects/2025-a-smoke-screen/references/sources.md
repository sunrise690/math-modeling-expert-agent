# 来源与输入账本

统一运行编号：`cumcm-2025a-20260808-r3`。访问日期均为北京时间 2026-08-08。

| 资源 | 类型 | URL / 本地路径 | SHA-256 / 版本 | 用途 |
|---|---|---|---|---|
| 2025 年高教社杯全国大学生数学建模竞赛赛题 | 官方网页 | https://www.mcm.edu.cn/html_cn/node/03c91a444e62eee81a3740fa97a461a6.html | 官方页面，发布于 2025-09-04 | 核验赛题来源与官方压缩包入口 |
| CUMCM2025Problems.zip | 官方附件 | https://www.mcm.edu.cn/upload_cn/node/759/SvpohSGacdffe718bcaa3b6e835c03ae3461cab1.zip | `cef6262c24ee3017bdab4ca255299c7b47b2700ad89fd773addde7e241e7e4de` | 原始赛题包；不纳入公开 Git 仓库 |
| A 题题面 | 官方输入 | `source/A题.pdf` | `a37f6aad30b16ea09da9cb320ce194b12d3a28874008cf9ff19549f6c6079447` | 初始条件、运动规律、五问任务 |
| 结果表 1 | 官方模板 | `source/result1.xlsx` | `af04b16e6a4719628971bcf5a03d230c9da6738e67eebac9276d254fdd4df1a7` | Q3 提交字段与回读核验 |
| 结果表 2 | 官方模板 | `source/result2.xlsx` | `c681d5e378538f71c77fca199a3ca8303a04dbcfc7bd95f870ae22f01ab69f91` | Q4 提交字段与回读核验 |
| 结果表 3 | 官方模板 | `source/result3.xlsx` | `b648c82d63e459ba6e6b3711ae79875e373521cd543b45571c4d8ff1ad5ec54a` | Q5 提交字段与回读核验 |
| Differential Evolution | 方法文献 | https://doi.org/10.1023/A:1008202821328 | Storn & Price, 1997 | Q2 全局候选搜索 |
| Numerical Optimization | 方法文献 | Nocedal & Wright, 2nd ed., 2006 | ISBN 978-0-387-30303-1 | 连续优化与数值诊断 |
| Integer and Combinatorial Optimization | 方法文献 | Nemhauser & Wolsey, 1988 | ISBN 978-0-471-82819-8 | 区间组合与有限状态搜索背景 |

## 公开复现边界

官方 PDF、XLSX 与 ZIP 不随 Git 发布，以避免重复分发竞赛方文件。复现者需从上表官方页面下载压缩包，将四个文件放入 `source/`，并运行 `Get-FileHash -Algorithm SHA256` 与本表及 `source/MANIFEST.sha256` 比对。哈希不一致时，项目门禁必须失败，不能用近似题面或改写模板替代。

本项目没有使用外部题解、答案汇总或获奖论文中的数值校准 2025 A 题结果；优秀论文仅用于抽取通用写作和证据链缺陷模式，记录在 Agent 的 skill 参考资料中。

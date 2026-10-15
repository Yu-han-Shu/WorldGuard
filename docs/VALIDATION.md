# 发布验证（2026-10-15）

现有 Windows 环境：Python 全套 178 通过；React TypeScript/Vite 构建通过；前端 6 项通过、1 项集成测试跳过；Node AGH 保护层 MOCK 测试 15 项通过。

材料整理期间发现 CLI 重放固定使用参考规划器，无法匹配 JSON Strategy A* 案例。已改为按保存的策略参数选择规划器；针对重放与上传策略的集成检查 10 项通过。三份公开案例均实际重放，matches=true，模型请求为 0。

原始样例文件不改写；manifest 使用 contracts.canonical 的 JSON 规范化 SHA-256，不是格式化文本的文件字节 SHA-256。另附发布文件 SHA256SUMS.json。

尚未完成：全新机器端到端安装、独立第三方验收、公平预算下 Agent 增量对照、实机实验。不能把 MOCK / REPLAY 等同 LIVE。官方网页原生轨迹导出仍需解决隔离 Host 会话的识别问题。

发布副本已使用独立 PYTHONPATH 指向副本源码，再次执行 178 项 Python 测试通过（73.82 秒）。依赖仍复用本机环境，不等于新机安装。GitHub CI 配置已加入，远端状态须以实际运行结果为准。

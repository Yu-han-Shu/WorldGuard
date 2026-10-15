# 发布验证（2026-10-15）

GitHub 全新 Linux runner 已安装依赖并通过完整检查：[CI 记录](https://github.com/Yu-han-Shu/WorldGuard/actions/runs/38674318227)。

- Python：178 项通过。
- AGH 保护层 MOCK：15 项通过。
- 前端：6 项通过，1 项需要服务的集成检查跳过；TypeScript / Vite 生产构建通过。
- Windows 发布副本：178 项 Python 测试通过；三类案例均离线重放 matches=true，模型调用 0。

材料整理时发现 CLI 重放固定使用参考规划器，无法匹配 JSON Strategy A* 案例。已改为按保存的策略参数选择规划器；相关上传策略与重放集成检查 10 项通过。原始样例未改写。

案例 manifest 使用规范化 JSON SHA-256；文件清单 SHA256SUMS.json 使用文件字节哈希。真实 Host 脱敏记录及核心工具调用链证明模型执行，MOCK 与离线重放不替代 LIVE。

当前验证覆盖安装、测试与构建；不代表完成新机器完整 LIVE 交互、独立第三方终验、公平预算下 Agent 优势对照或实机实验。

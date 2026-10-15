# final_v1 实测结果

来源：experiments/final_v1/results/raw.json；逐例结果、oracle、哈希、重放均保留。
协议在运行前冻结，见 protocol.json / protocol.sha256 / versions.json。

| 方法 | 案例 | 原始 FAIL | 原始 UNKNOWN | 恢复后到达 | SAFE_STOP | 失败重放一致 |
|---|---|---|---|---|---|---|
| reference_current | 12 | 0 | 5 | 7 | 5 | 0/0 |
| TEST_MUTANT_stale_view | 12 | 8 | 0 | 7 | 5 | 8/8 |

上述两个方法在相同 12 个最终案例上成对执行；UNKNOWN 空路径并未计为错误放行。
正确停止仅按独立有限网格 oracle 判定，不能推广为任意连续轨迹无路。
TEST_MUTANT_stale_view 是显式测试夹具，不是旧仓库已证实漏洞。
危险检出率/误报率留 null：没有独立标注的候选路径真值数据集，避免验收器给自己打分。
E2、AgnesAGH=NOT_RUN，旧导航适配器=BLOCKED；不能宣称 Agent 优于固定/随机/规则，也没有人工工时节省数据。
模型调用 0；tokens/费用 null。小样本只支持本范围内的描述性结果。

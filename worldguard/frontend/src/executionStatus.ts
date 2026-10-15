type TimedRecord = { timestamp: string };

/** Only observed records advance the activity display; elapsed time never does. */
export function executionActivity({
  events,
  decisions,
  createdAt,
  now,
  connected,
  jobActive,
  manual = false,
  interrupted = false,
}: {
  events: TimedRecord[];
  decisions: TimedRecord[];
  createdAt: string | null;
  now: number;
  connected: boolean;
  jobActive: boolean;
  manual?: boolean;
  interrupted?: boolean;
}) {
  const times = [...events, ...decisions]
    .map((item) => Date.parse(item.timestamp))
    .filter(Number.isFinite);
  const lastAt = times.length ? Math.max(...times) : Date.parse(createdAt || "");
  const idleSeconds = Number.isFinite(lastAt)
    ? Math.max(0, Math.floor((now - lastAt) / 1000))
    : null;
  return {
    idleSeconds,
    title: !connected
      ? "连接暂时中断"
      : interrupted
        ? "执行已中断"
        : manual && !jobActive
          ? "等待手动操作"
      : !jobActive
        ? "等待任务调度"
        : !events.length && !decisions.length
          ? "等待首条执行记录"
          : "等待下一步结果",
    description: !connected
      ? "正在重新连接。下方保留最后收到的记录，当前执行状态暂未更新。"
      : interrupted
        ? "这次执行已中断，已有记录仍可查看；继续评测需要新建任务。"
        : manual && !jobActive
          ? "这是一条手动运行记录，系统不会自动执行下一步。"
      : !jobActive
        ? "任务已提交，执行开始后会在这里显示实际动作。"
        : idleSeconds !== null && idleSeconds >= 20
          ? "暂时没有新记录。模型响应或工具执行可能需要一些时间，新记录到达后会自动更新。"
          : "每次工具返回与公开决策都会更新在这里，可以同时查看下方地图。",
  };
}

export function elapsedLabel(seconds: number) {
  const total = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  return total < 60 ? `${total} 秒` : `${Math.floor(total / 60)} 分 ${total % 60} 秒`;
}

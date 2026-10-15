/** Merge only occupied cells: visual objects keep exactly the audited footprint. */
export function mergeCells(cells: number[][]) {
  const remaining = new Set(cells.map(([r, c]) => `${r},${c}`));
  const blocks: { row: number; col: number; width: number; height: number }[] =
    [];
  for (const [row, col] of [...cells].sort(
    (a, b) => a[0] - b[0] || a[1] - b[1],
  )) {
    if (!remaining.has(`${row},${col}`)) continue;
    let width = 1,
      height = 1;
    while (remaining.has(`${row},${col + width}`)) width++;
    while (
      Array.from({ length: width }, (_, i) =>
        remaining.has(`${row + height},${col + i}`),
      ).every(Boolean)
    )
      height++;
    for (let r = row; r < row + height; r++)
      for (let c = col; c < col + width; c++) remaining.delete(`${r},${c}`);
    blocks.push({ row, col, width, height });
  }
  return blocks;
}
export function pathSample(path: number[][], fraction: number) {
  const lengths = path
    .slice(1)
    .map((p, i) => Math.hypot(p[0] - path[i][0], p[1] - path[i][1]));
  const total = lengths.reduce((sum, n) => sum + n, 0);
  let distance = total * Math.max(0, Math.min(1, fraction));
  for (let i = 0; i < lengths.length; i++) {
    if (
      lengths[i] > 0 &&
      (distance <= lengths[i] || i === lengths.length - 1)
    ) {
      const t = distance / lengths[i],
        a = path[i],
        b = path[i + 1];
      return {
        point: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t],
        angle: (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI,
        total,
      };
    }
    distance -= lengths[i];
  }
  return { point: path.at(-1) || [], angle: 0, total };
}

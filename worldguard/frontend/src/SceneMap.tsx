import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  Crosshair,
  Grid2X2,
  Minus,
  Plus,
  Play,
  Pause,
  RotateCcw,
  Scan,
  X,
} from "lucide-react";
import type { Case } from "../client";
import type { components } from "../schema";
import { mergeCells, pathSample } from "./mapGeometry";
type Scene = components["schemas"]["SceneView"];
type Task = components["schemas"]["TaskView"];
const roles = { original: "原始路径", recovery: "恢复路径", rerun: "复测路径" };
const colors = { original: "#f4b957", recovery: "#81e6d2", rerun: "#bd9cff" };
export function SceneMap({
  scene,
  task,
  paths = [],
  before,
  risk = false,
  compact = false,
  playback = false,
  pathColor,
  timelineProgress,
}: {
  scene: Scene;
  task: Task;
  paths?: Case["paths"];
  before?: Scene;
  risk?: boolean;
  compact?: boolean;
  playback?: boolean;
  pathColor?: string;
  timelineProgress?: number;
}) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [zoom, setZoom] = useState(1),
    [pan, setPan] = useState([0, 0]);
  const [grid, setGrid] = useState(false),
    [footprint, setFootprint] = useState(false);
  const [hidden, setHidden] = useState<string[]>([]),
    [selected, setSelected] = useState("");
  const [progress, setProgress] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1);
  const [inspected, setInspected] = useState<string | null>(null);
  const drag = useRef<{
    x: number;
    y: number;
    pan: number[];
    scale: number;
  } | null>(null);
  const w = scene.width * 20,
    h = scene.height * 20;
  const active = paths.find((p) => p.path_id === selected) || paths.at(-1);
  const route = active?.plan.path || [];
  const sample = pathSample(route, (timelineProgress ?? progress) / 100);
  useEffect(() => {
    setProgress(0);
    setPlaying(false);
    setInspected(null);
  }, [scene.content_hash, active?.path_id]);
  useEffect(() => {
    setPan([0, 0]);
    setZoom(1);
  }, [scene.scene_id]);
  useEffect(() => {
    if (!playing || !playback || route.length < 2) return;
    const timer = window.setInterval(
      () => setProgress((value) => Math.min(100, value + speed / 3)),
      40,
    );
    return () => window.clearInterval(timer);
  }, [playing, speed, playback, route.length]);
  useEffect(() => {
    if (progress >= 100) setPlaying(false);
  }, [progress]);
  const blocks = useMemo(() => {
    const known = new Set(
      (before?.occupied || scene.occupied).map((c) => c.join(",")),
    );
    return {
      fixed: mergeCells(scene.occupied.filter((c) => known.has(c.join(",")))),
      fault: mergeCells(scene.occupied.filter((c) => !known.has(c.join(",")))),
    };
  }, [scene.occupied, before?.occupied]);
  const xy = (p: number[]) => [
    ((p[0] - scene.origin_xy_m[0]) / scene.resolution_m) * 20,
    h - ((p[1] - scene.origin_xy_m[1]) / scene.resolution_m) * 20,
  ];
  const violations = paths.flatMap((p) => p.audit?.audit.violations || []);
  const start = xy(task.start_xy_m),
    goal = xy(task.goal_xy_m);
  const robot = xy(sample.point.length ? sample.point : task.start_xy_m);
  const radius = (task.robot.radius_m / scene.resolution_m) * 20;
  const required =
    ((task.robot.radius_m + task.robot.clearance_margin_m) /
      scene.resolution_m) *
    20;
  const symbolScale = Math.max(1, Math.min(1.9, scene.width / 40));
  const toggle = (key: string) =>
    setHidden((value) =>
      value.includes(key) ? value.filter((x) => x !== key) : [...value, key],
    );
  return (
    <div
      className={`scene-map ${compact ? "compact" : ""} ${playback ? "with-playback" : ""}`}
    >
      <div className="map-canvas">
        <svg
          viewBox={`-24 -24 ${w + 48} ${h + 48}`}
          role="img"
          aria-label={`${scene.scene_id} 的真实地图、障碍与路径`}
          data-testid="case-map"
          style={{ touchAction: compact ? "auto" : "none" }}
          onPointerDown={(e) => {
            if (compact) return;
            e.currentTarget.setPointerCapture(e.pointerId);
            const rect = e.currentTarget.getBoundingClientRect();
            drag.current = {
              x: e.clientX,
              y: e.clientY,
              pan,
              scale: Math.max((w + 48) / rect.width, (h + 48) / rect.height),
            };
          }}
          onPointerMove={(e) => {
            const d = drag.current;
            if (d)
              setPan([
                d.pan[0] + (e.clientX - d.x) * d.scale,
                d.pan[1] + (e.clientY - d.y) * d.scale,
              ]);
          }}
          onPointerUp={() => {
            drag.current = null;
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
        >
          <defs>
            <linearGradient id={`${uid}floor`} x2="0.6" y2="1">
              <stop stopColor="#303c42" />
              <stop offset="1" stopColor="#1d282e" />
            </linearGradient>
            <pattern
              id={`${uid}tiles`}
              width="80"
              height="80"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M80 0H0V80"
                fill="none"
                stroke="#93b6c7"
                strokeOpacity=".09"
              />
              <path d="M5 5h4m-4 0v4" stroke="#314556" />
            </pattern>
            <pattern
              id={`${uid}grid`}
              width="20"
              height="20"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M20 0H0V20"
                fill="none"
                stroke="#48a4c7"
                strokeOpacity=".3"
                strokeWidth=".6"
              />
            </pattern>
            <linearGradient id={`${uid}steel`} x2="1" y2=".3">
              <stop stopColor="#587083" />
              <stop offset=".22" stopColor="#26394a" />
              <stop offset=".76" stopColor="#192c3c" />
              <stop offset="1" stopColor="#54768c" />
            </linearGradient>
            <pattern
              id={`${uid}cargo`}
              width="42"
              height="50"
              patternUnits="userSpaceOnUse"
            >
              <rect width="42" height="50" fill="#132335" />
              <rect
                x="3"
                y="3"
                width="35"
                height="43"
                rx="2"
                fill="#415165"
                stroke="#728096"
                strokeWidth=".8"
              />
              <rect x="6" y="7" width="13" height="16" fill="#687079" />
              <rect x="21" y="7" width="14" height="16" fill="#696050" />
              <rect x="6" y="26" width="29" height="16" fill="#304b65" />
              <path
                d="M12 7v16m16-16v16M6 34h29M3 47h35"
                stroke="#a3a9a5"
                strokeOpacity=".5"
              />
            </pattern>
            <pattern
              id={`${uid}wall`}
              width="32"
              height="32"
              patternUnits="userSpaceOnUse"
            >
              <rect width="32" height="32" fill={`url(#${uid}steel)`} />
              <path d="M0 0H32V32" stroke="#728899" strokeWidth="1" />
              <circle cx="4" cy="4" r="1.5" fill="#101c27" />
            </pattern>
            <pattern
              id={`${uid}stripe`}
              width="14"
              height="14"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="7" height="14" fill="#f6b94a" />
              <rect x="7" width="7" height="14" fill="#192b3c" />
            </pattern>
            <pattern
              id={`${uid}hazard`}
              width="14"
              height="14"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="14" height="14" fill="#d9435433" />
              <rect width="3" height="14" fill="#ff566a" fillOpacity=".65" />
            </pattern>
            <radialGradient id={`${uid}heat`}>
              <stop stopColor="#ff435f" stopOpacity=".8" />
              <stop offset=".45" stopColor="#ff9035" stopOpacity=".4" />
              <stop offset="1" stopColor="#ffc13d" stopOpacity="0" />
            </radialGradient>
            <filter
              id={`${uid}glow`}
              x="-70%"
              y="-70%"
              width="240%"
              height="240%"
            >
              <feGaussianBlur stdDeviation="4" />
            </filter>
            <clipPath id={`${uid}bounds`}>
              <rect x="-20" y="-20" width={w + 40} height={h + 40} rx="8" />
            </clipPath>
            <linearGradient id={`${uid}robot`} x2="0" y2="1">
              <stop stopColor="#edf8ff" />
              <stop offset=".45" stopColor="#718a9c" />
              <stop offset="1" stopColor="#d2e5f0" />
            </linearGradient>
          </defs>
          <g clipPath={`url(#${uid}bounds)`}>
            <g
              transform={`translate(${pan[0] + w / 2} ${pan[1] + h / 2}) scale(${zoom}) translate(${-w / 2} ${-h / 2})`}
            >
              <rect
                x="-10"
                y="-10"
                width={w + 20}
                height={h + 20}
                rx="3"
                fill="#04111d"
                stroke="#359aca"
                strokeWidth="2"
              />
              <rect width={w} height={h} fill={`url(#${uid}floor)`} />
              <rect width={w} height={h} fill={`url(#${uid}tiles)`} />
              {!scene.scene_id.startsWith("challenge_") && (
                <path
                  d={`M25 ${start[1] - 38}H${w - 25}M25 ${start[1] + 38}H${w - 25}`}
                  stroke="#527086"
                  strokeWidth="1.5"
                  strokeDasharray="12 12"
                  opacity=".45"
                />
              )}
              {!scene.scene_id.startsWith("challenge_") &&
                Array.from({ length: Math.ceil(w / 200) }, (_, i) => (
                  <path
                    key={i}
                    d={`M${80 + i * 200} ${start[1]}h20l-6 -5m6 5l-6 5`}
                    stroke="#5c7b90"
                    strokeWidth="2"
                    fill="none"
                    opacity=".45"
                  />
                ))}
              {blocks.fixed.map((b, i) => {
                const x = b.col * 20,
                  y = h - (b.row + b.height) * 20,
                  bw = b.width * 20,
                  bh = b.height * 20;
                const wall =
                  Math.min(b.width, b.height) <= 2 ||
                  b.width * b.height > 180 ||
                  (scene.scene_id.startsWith("terminal_") && b.width <= 2);
                const info = `${wall ? "隔墙 / 固定障碍" : "货架 / 设备岛"} ${String(i + 1).padStart(2, "0")} · ${(b.width * scene.resolution_m).toFixed(2)} × ${(b.height * scene.resolution_m).toFixed(2)} m · 栅格 [${b.row}, ${b.col}]`;
                return (
                  <g
                    key={i}
                    className={!compact ? "map-object" : undefined}
                    onPointerDown={() => {
                      if (!compact) setInspected(info);
                    }}
                  >
                    <title>{info}</title>
                    <rect
                      x={x + 4}
                      y={y + 5}
                      width={bw}
                      height={bh}
                      rx="2"
                      fill="#02080f"
                      opacity=".75"
                    />
                    <rect
                      x={x}
                      y={y}
                      width={bw}
                      height={bh}
                      fill={wall ? `url(#${uid}wall)` : `url(#${uid}steel)`}
                      stroke="#658294"
                      strokeWidth="1.4"
                    />
                    {!wall && (
                      <>
                        <rect
                          x={x + 5}
                          y={y + 5}
                          width={Math.max(1, bw - 10)}
                          height={Math.max(1, bh - 10)}
                          fill={`url(#${uid}cargo)`}
                        />
                        <path
                          d={`M${x + 3} ${y + 3}v${bh - 6}M${x + bw - 3} ${y + 3}v${bh - 6}`}
                          stroke="#2395cd"
                          strokeWidth="2.5"
                        />
                        {[0, 1].map((n) => (
                          <rect
                            key={n}
                            x={x + 2}
                            y={y + n * (bh - 5)}
                            width={bw - 4}
                            height="5"
                            fill={`url(#${uid}stripe)`}
                          />
                        ))}
                        {bw > 60 && bh > 60 && (
                          <g>
                            <rect
                              x={x + 9}
                              y={y + bh / 2 - 8}
                              width="34"
                              height="16"
                              rx="2"
                              fill="#062c48"
                              stroke="#4c85a4"
                            />
                            <text
                              x={x + 26}
                              y={y + bh / 2 + 4}
                              textAnchor="middle"
                              fontSize="10"
                              fill="#b6d6e7"
                            >
                              {String(i + 1).padStart(2, "0")}
                            </text>
                          </g>
                        )}
                      </>
                    )}
                    {wall && (
                      <path
                        d={`M${x + 2} ${y + 2}h${bw - 4}`}
                        stroke="#8aa8bc"
                        strokeWidth="2"
                      />
                    )}
                  </g>
                );
              })}
              {!hidden.includes("fault") &&
                blocks.fault.map((b, i) => {
                  const x = b.col * 20,
                    y = h - (b.row + b.height) * 20,
                    bw = b.width * 20,
                    bh = b.height * 20;
                  return (
                    <g key={i}>
                      <rect
                        x={x}
                        y={y}
                        width={bw}
                        height={bh}
                        fill={`url(#${uid}hazard)`}
                        stroke="#ff596b"
                        strokeWidth="2"
                      />
                      <g transform={`translate(${x + bw / 2} ${y + bh / 2})`}>
                        <circle r="14" fill="#661e2d" stroke="#ff7788" />
                        <text
                          textAnchor="middle"
                          y="6"
                          fill="white"
                          fontWeight="800"
                          fontSize="20"
                        >
                          !
                        </text>
                      </g>
                    </g>
                  );
                })}
              {scene.scene_id.startsWith("challenge_") &&
                !compact &&
                ["A · 接收区", "B · 存储区", "C · 分拣区", "D · 出库区"].map(
                  (label, i) => (
                    <g
                      key={label}
                      transform={`translate(${(i * 22 + 9) * 20} 28)`}
                    >
                      <rect
                        x="-76"
                        y="-10"
                        width="152"
                        height="39"
                        rx="5"
                        fill="#18272ce8"
                        stroke="#658284"
                      />
                      <text
                        x="0"
                        y="17"
                        textAnchor="middle"
                        fill="#b9ccca"
                        fontSize="23"
                      >
                        {label}
                      </text>
                    </g>
                  ),
                )}
              {scene.unknown.map(([r, c]) => (
                <rect
                  key={`${r}-${c}`}
                  x={c * 20}
                  y={h - (r + 1) * 20}
                  width="20"
                  height="20"
                  fill="#a480cc66"
                  stroke="#bd9cff"
                  strokeDasharray="3 2"
                >
                  <title>未知栅格</title>
                </rect>
              ))}
              {grid && (
                <rect
                  width={w}
                  height={h}
                  fill={`url(#${uid}grid)`}
                  pointerEvents="none"
                />
              )}
              {risk &&
                violations.map((v, i) => {
                  const p = v.obstacle_xy_m as number[] | undefined;
                  return p ? (
                    <circle
                      key={i}
                      cx={xy(p)[0]}
                      cy={xy(p)[1]}
                      r="75"
                      fill={`url(#${uid}heat)`}
                    />
                  ) : null;
                })}
              {paths
                .filter((p) => !hidden.includes(p.role))
                .map((p) => {
                  const d = p.plan.path
                    .map(xy)
                    .map((pt) => pt.join(","))
                    .join(" ");
                  return (
                    <g key={p.path_id}>
                      <polyline
                        points={d}
                        fill="none"
                        stroke={pathColor || colors[p.role]}
                        strokeWidth="10"
                        opacity=".5"
                        filter={`url(#${uid}glow)`}
                      />
                      <polyline
                        points={d}
                        fill="none"
                        stroke={pathColor || colors[p.role]}
                        strokeWidth={compact ? "6" : "3.5"}
                        strokeDasharray={
                          p.role === "original"
                            ? "11 7"
                            : p.role === "rerun"
                              ? "3 5"
                              : undefined
                        }
                        strokeLinejoin="round"
                        strokeLinecap="round"
                      />
                      {!compact &&
                        p.plan.path.length > 1 &&
                        [0.22, 0.52, 0.8].map((fraction) => {
                          const marker = pathSample(p.plan.path, fraction),
                            point = xy(marker.point);
                          return (
                            <path
                              key={fraction}
                              d="M-7 -6L1 0L-7 6"
                              transform={`translate(${point[0]} ${point[1]}) rotate(${-marker.angle})`}
                              fill="none"
                              stroke={pathColor || colors[p.role]}
                              strokeWidth="3"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          );
                        })}
                      {p.audit?.audit.violations.map((v, i) => {
                        const seg = v.segment_xy_m as number[][] | undefined;
                        return seg ? (
                          <polyline
                            key={i}
                            points={seg
                              .map(xy)
                              .map((pt) => pt.join(","))
                              .join(" ")}
                            fill="none"
                            stroke="#ff5d73"
                            strokeWidth="5"
                          >
                            <title>独立审计：违规线段</title>
                          </polyline>
                        ) : null;
                      })}
                    </g>
                  );
                })}
              {[
                [start, "S", "#00e4b8"],
                [goal, "G", "#ff617b"],
              ].map(([pos, name, color]) => {
                const [x, y] = pos as number[];
                return (
                  <g key={String(name)} transform={`translate(${x} ${y})`}>
                    <circle r="26" fill={String(color)} opacity=".12" />
                    <circle
                      r="17"
                      fill="#071c2d"
                      stroke={String(color)}
                      strokeWidth="3"
                    />
                    <text
                      y="6"
                      textAnchor="middle"
                      fill={String(color)}
                      fontSize="18"
                      fontWeight="700"
                    >
                      {String(name)}
                    </text>
                    <text
                      y="38"
                      textAnchor="middle"
                      fill="#d4e6f5"
                      fontSize="12"
                    >
                      {name === "S" ? "起点" : "终点"}
                    </text>
                  </g>
                );
              })}
              {(!compact ||
                (timelineProgress !== undefined && route.length > 0)) && (
                <g
                  data-replay-robot
                  transform={`translate(${robot[0]} ${robot[1]})`}
                >
                  {footprint && (
                    <>
                      <circle
                        r={required}
                        fill="#1ee5dc1a"
                        stroke="#50ffe9"
                        strokeWidth="1"
                        strokeDasharray="3 3"
                      />
                      <circle
                        r={radius}
                        fill="none"
                        stroke="#b5e5ff"
                        strokeWidth=".8"
                      />
                    </>
                  )}
                  <g
                    transform={`rotate(${-sample.angle}) scale(${symbolScale})`}
                  >
                    <ellipse
                      rx="20"
                      ry="17"
                      fill="#13a9f4"
                      opacity=".23"
                      filter={`url(#${uid}glow)`}
                    />
                    <rect
                      x="-13"
                      y="-14"
                      width="20"
                      height="5"
                      rx="2"
                      fill="#030c17"
                    />
                    <rect
                      x="-13"
                      y="9"
                      width="20"
                      height="5"
                      rx="2"
                      fill="#030c17"
                    />
                    <rect
                      x="-17"
                      y="-11"
                      width="34"
                      height="22"
                      rx="7"
                      fill={`url(#${uid}robot)`}
                      stroke="#8cc8eb"
                    />
                    <rect
                      x="-10"
                      y="-8"
                      width="18"
                      height="16"
                      rx="4"
                      fill="#0b1b2e"
                    />
                    <circle r="5" fill="#102d46" stroke="#36dcff" />
                    <rect
                      x="12"
                      y="-6"
                      width="3"
                      height="12"
                      rx="1"
                      fill="#7cf6ff"
                    />
                    <circle cx="5" cy="-4" r="1.5" fill="#b7f8ff" />
                  </g>
                  <rect
                    x={-40 * symbolScale}
                    y={-44 * symbolScale}
                    width={80 * symbolScale}
                    height={19 * symbolScale}
                    rx="4"
                    fill="#06233a"
                    stroke="#2a80ac"
                  />
                  <text
                    y={-31 * symbolScale}
                    textAnchor="middle"
                    fill="#d6f5ff"
                    fontSize={10 * symbolScale}
                  >
                    {playback && route.length
                      ? "AMR · 路径预览"
                      : "AMR · 起点示意"}
                  </text>
                </g>
              )}
              <path
                d={`M12 5h40M${w - 52} 5h40M12 ${h - 5}h40M${w - 52} ${h - 5}h40`}
                stroke="#32bcff"
                strokeWidth="4"
              />
            </g>
          </g>
        </svg>
        {!compact && (
          <>
            <div className="map-tag">
              <span className="live-dot" />
              二维场景 <b>SCENE / {String(scene.revision).padStart(2, "0")}</b>
            </div>
            <div className="map-tools">
              <button
                title="放大地图"
                aria-label="放大地图"
                onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
              >
                <Plus size={17} />
              </button>
              <button
                title="缩小地图"
                aria-label="缩小地图"
                onClick={() => setZoom((z) => Math.max(0.75, z - 0.25))}
              >
                <Minus size={17} />
              </button>
              <button
                title="适应画布"
                aria-label="重置视图"
                onClick={() => {
                  setZoom(1);
                  setPan([0, 0]);
                }}
              >
                <Crosshair size={17} />
              </button>
              <button
                title="显示审计网格"
                aria-label="显示审计网格"
                aria-pressed={grid}
                onClick={() => setGrid(!grid)}
              >
                <Grid2X2 size={17} />
              </button>
              <button
                title="显示机器人足迹"
                aria-label="显示机器人足迹"
                aria-pressed={footprint}
                onClick={() => setFootprint(!footprint)}
              >
                <Scan size={17} />
              </button>
            </div>
            {inspected && (
              <div className="object-info">
                {inspected}
                <button
                  aria-label="关闭地图元素详情"
                  onClick={() => setInspected(null)}
                >
                  <X size={12} />
                </button>
              </div>
            )}
            <div className="map-coords">
              {(scene.width * scene.resolution_m).toFixed(1)} ×{" "}
              {(scene.height * scene.resolution_m).toFixed(1)} m ·{" "}
              {Math.round(zoom * 100)}% · 拖动平移
            </div>
          </>
        )}
      </div>
      {!compact && (
        <div className="map-layerbar" aria-label="地图显示内容">
          <span
            className="map-layer-title"
            title="点击路径或新增障碍可切换显示；不会改变地图数据和评测结果。"
          >
            {paths.length ? "显示内容" : "地图图例"}
          </span>
          {(["original", "recovery", "rerun"] as const)
            .filter((role) => paths.some((p) => p.role === role))
            .map((role) => (
              <button
                key={role}
                aria-pressed={!hidden.includes(role)}
                title={
                  (hidden.includes(role) ? "显示" : "隐藏") +
                  roles[role] +
                  "，不改变评测结果"
                }
                onClick={() => toggle(role)}
              >
                <i style={{ background: colors[role] }} />
                {roles[role]}
              </button>
            ))}
          {!!blocks.fault.length && (
            <button
              aria-pressed={!hidden.includes("fault")}
              title={
                (hidden.includes("fault") ? "显示" : "隐藏") +
                "新增障碍，不改变评测结果"
              }
              onClick={() => toggle("fault")}
            >
              <i className="hazard-key" />
              新增障碍
            </button>
          )}
          <span className="map-material-key">
            <i />
            固定障碍
          </span>
          <span className="map-resolution">{scene.resolution_m} m / 格</span>
          {paths.length > 0 && (
            <span className="map-layer-hint">
              点击图例可隐藏 / 显示，不影响评测
            </span>
          )}
        </div>
      )}
      {!compact && playback && (
        <div className="route-playback">
          <div className="playback-heading">
            <strong>路径回放</strong>
            <span>按距离预览 · 非真实运动记录</span>
            <select
              aria-label="回放路径"
              value={active?.path_id || ""}
              onChange={(e) => setSelected(e.target.value)}
              disabled={!paths.length}
            >
              {paths.length ? (
                paths.map((p, i) => (
                  <option key={p.path_id} value={p.path_id}>
                    {roles[p.role]} {i + 1} · {p.audit_status}
                  </option>
                ))
              ) : (
                <option value="">暂无路径</option>
              )}
            </select>
          </div>
          <div className="playback-controls">
            <button
              aria-label={playing ? "暂停路径回放" : "播放路径回放"}
              disabled={route.length < 2}
              onClick={() => {
                if (progress >= 100) setProgress(0);
                setPlaying(!playing);
              }}
            >
              {playing ? <Pause size={17} /> : <Play size={17} />}
            </button>
            <button
              aria-label="重置路径回放"
              disabled={!route.length}
              onClick={() => {
                setProgress(0);
                setPlaying(false);
              }}
            >
              <RotateCcw size={15} />
            </button>
            <input
              aria-label="路径回放进度"
              type="range"
              min="0"
              max="100"
              step=".1"
              value={progress}
              disabled={route.length < 2}
              onChange={(e) => {
                setPlaying(false);
                setProgress(Number(e.target.value));
              }}
            />
            <span>{Math.round(progress)}%</span>
            <select
              aria-label="回放速度"
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            >
              <option value=".5">0.5×</option>
              <option value="1">1×</option>
              <option value="2">2×</option>
            </select>
          </div>
          <div
            className={`playback-note ${active?.audit_status === "FAIL" ? "danger" : ""}`}
          >
            {active?.audit_status === "FAIL"
              ? "未通过审计的候选路径 · 仅展示问题，未作为安全路线执行"
              : route.length
                ? `路径长度 ${sample.total.toFixed(2)} m · 图标仅示意位置，足迹图层展示真实几何尺寸`
                : "执行案例后即可查看原始与恢复路径"}
          </div>
        </div>
      )}
    </div>
  );
}

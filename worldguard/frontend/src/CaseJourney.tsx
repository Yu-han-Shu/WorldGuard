import { useEffect, useState } from "react";
import { Check, FileText, TriangleAlert } from "lucide-react";
import type { Case } from "../client";
import { SceneMap } from "./SceneMap";
import { title } from "./useWorkbench";

export function CaseJourney({
  value,
  comparison = false,
  onEvidence,
}: {
  value: Case;
  comparison?: boolean;
  onEvidence: (id: string) => void;
}) {
  const [phase, setPhase] = useState("all");
  useEffect(() => setPhase("all"), [value.candidate.case_id]);
  const original = value.paths.find((p) => p.role === "original");
  const recovery = value.paths.findLast((p) => p.role === "recovery");
  const phases = [
    {
      id: "before",
      label: "原始环境",
      scene: value.scene_before,
      // The recorded audit concerns the post-injection map, not this preview.
      paths: original
        ? [{ ...original, audit: null, audit_status: "NOT_RUN" as const }]
        : [],
    },
    {
      id: "fault",
      label: "注入障碍",
      scene: value.scene_after,
      paths: original ? [original] : [],
    },
    {
      id: "recovery",
      label: "恢复路线",
      scene: value.scene_after,
      paths: recovery ? [recovery] : [],
    },
  ];
  const selected = phases.find((p) => p.id === phase);
  const length = (path?: Case["paths"][number]) =>
    path?.plan.path.length
      ? path.plan.path
          .slice(1)
          .reduce(
            (sum, p, i) =>
              sum +
              Math.hypot(
                p[0] - path.plan.path[i][0],
                p[1] - path.plan.path[i][1],
              ),
            0,
          )
          .toFixed(2) + " m"
      : "—";
  const clearance = (path?: Case["paths"][number]) =>
    typeof path?.audit?.audit.minimum_remaining_clearance_m === "number"
      ? path.audit.audit.minimum_remaining_clearance_m.toFixed(3) + " m"
      : "—";
  if (comparison)
    return (
      <div className="studio-comparison-view">
        <div className="studio-comparison-maps">
          {[
            { label: "原始路线", path: original },
            { label: "恢复路线", path: recovery },
          ].map((item) => (
            <figure key={item.label}>
              <figcaption
                className={
                  item.path?.audit_status === "PASS"
                    ? "green"
                    : item.path?.audit_status === "FAIL"
                      ? "red"
                      : "muted"
                }
              >
                {item.path?.audit_status === "PASS" ? (
                  <Check size={15} />
                ) : (
                  <TriangleAlert size={15} />
                )}{" "}
                {item.label} · {title(item.path?.audit_status || "NOT_RUN")}
              </figcaption>
              <SceneMap
                scene={value.scene_after}
                before={value.scene_before}
                task={value.task}
                paths={item.path ? [item.path] : []}
                compact
              />
            </figure>
          ))}
        </div>
        <p className="studio-comparison-note">
          同一真实地图 · 同一机器人尺寸 · 同一独立验收规则
        </p>
        <table className="studio-metric-table">
          <thead>
            <tr>
              <th>指标</th>
              <th>原始路线</th>
              <th>恢复路线</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>独立验收</td>
              <td>{title(original?.audit_status || "NOT_RUN")}</td>
              <td>{title(recovery?.audit_status || "NOT_RUN")}</td>
            </tr>
            <tr>
              <td>最小剩余净空</td>
              <td>{clearance(original)}</td>
              <td>{clearance(recovery)}</td>
            </tr>
            <tr>
              <td>路径长度</td>
              <td>{length(original)}</td>
              <td>{length(recovery)}</td>
            </tr>
          </tbody>
        </table>
        <div className="studio-comparison-evidence">
          {[original, recovery]
            .filter((p) => p?.audit?.evidence_id)
            .map((p) => (
              <button
                key={p!.path_id}
                onClick={() => onEvidence(p!.audit!.evidence_id!)}
              >
                <FileText size={14} />
                {p!.role === "original" ? "原始验收依据" : "恢复验收依据"}
              </button>
            ))}
        </div>
        {!recovery && (
          <p className="studio-artifact-note">
            该案例尚无恢复路线。停止或未执行不代表通过。
          </p>
        )}
      </div>
    );
  return (
    <div className="studio-journey">
      <SceneMap
        scene={selected?.scene || value.scene_after}
        before={phase === "before" ? undefined : value.scene_before}
        task={value.task}
        paths={selected?.paths || value.paths}
        playback
      />
      <div className="studio-journey-heading">
        <span>案例过程</span>
        <button aria-pressed={phase === "all"} onClick={() => setPhase("all")}>
          叠加对照
        </button>
      </div>
      <div className="studio-journey-steps">
        {phases.map((item, i) => (
          <button
            key={item.id}
            aria-pressed={phase === item.id}
            onClick={() => setPhase(item.id)}
            disabled={item.id === "recovery" && !recovery}
          >
            <SceneMap
              scene={item.scene}
              before={item.id === "before" ? undefined : value.scene_before}
              task={value.task}
              paths={item.paths}
              compact
            />
            <span>
              <small>0{i + 1}</small>
              {item.label}
              {item.id === "recovery" && !recovery ? " · 待执行" : ""}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

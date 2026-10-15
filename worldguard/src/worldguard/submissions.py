"""Bounded strategy intake. Uploaded Python is parsed, never imported or executed."""
import ast
import hashlib
import json

from worldguard.contracts import digest, identifier
from worldguard.evidence import read_json, write_json


def receive_submission(root, request):
    content = request.content
    if len(content.encode("utf-8")) > 64000:
        raise ValueError("FILE_TOO_LARGE_64KB")
    strategy, findings = None, []
    if request.filename.endswith(".json"):
        try:
            data = json.loads(content)
        except (ValueError, RecursionError):
            raise ValueError("INVALID_STRATEGY_JSON") from None
        if not isinstance(data, dict) or set(data) != {"schema_version", "planner", "turn_cost_m", "clearance_weight"}:
            raise ValueError("STRATEGY_FIELDS_REQUIRED")
        if data["schema_version"] != "worldguard-strategy/v1" or data["planner"] != "strategy_astar":
            raise ValueError("UNSUPPORTED_STRATEGY_VERSION")
        import math
        if any(type(data[k]) not in (int, float) or not math.isfinite(data[k]) or not 0 <= data[k] <= 5
               for k in ("turn_cost_m", "clearance_weight")):
            raise ValueError("STRATEGY_PARAMETERS_0_TO_5")
        strategy = data
        status = "READY"
        findings = ["格式与参数检查通过，将使用这份参数执行 Strategy A*。",
                    f"转弯代价 {data['turn_cost_m']} m；净空权重 {data['clearance_weight']}。",
                    "将在正常基准与地图变化案例中验证路线；这里尚未得出性能或安全结论。"]
    else:
        status = "STATIC_ONLY"
        try:
            tree = ast.parse(content)
            functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            entry = next((n for n in functions if n.name == "plan"), None)
            findings.append("Python 语法检查通过；没有执行、导入或安装文件中的任何代码。")
            if entry:
                args = [a.arg for a in (*entry.args.posonlyargs, *entry.args.args, *entry.args.kwonlyargs)]
                findings.append("检测到 plan(" + ", ".join(args) + ")。接口匹配仍需适配器验证。")
            else:
                findings.append("未找到顶层 plan 函数。建议暴露 plan(scene, task) 作为导航入口。")
            imports = sorted({n.names[0].name.split('.')[0] if isinstance(n, ast.Import) else (n.module or '').split('.')[0]
                              for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))})
            if imports:
                findings.append("声明的依赖：" + ", ".join(imports[:16]) + "；尚未验证可用性。")
        except (SyntaxError, ValueError, RecursionError):
            findings.append("Python 语法无法解析，请先修正文件。")
        findings.append("本机尚未接入代码隔离执行环境；Python 仅静态检查，不能启动导航评测。可上传 JSON 策略或使用示例体验。")
    value = {"filename": request.filename, "content": content, "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
             "status": status, "strategy": strategy, "findings": findings, "analysis_source": "STATIC_RULES"}
    value["submission_id"] = "submission_" + digest(value)[:24]
    folder = root / "submissions"
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / (value["submission_id"] + ".json"), value)
    return value


def read_submission(root, submission_id):
    identifier(submission_id)
    path = root / "submissions" / (submission_id + ".json")
    if not path.is_file() or path.is_symlink():
        raise ValueError("SUBMISSION_NOT_FOUND")
    value = read_json(path)
    if "submission_" + digest({k: v for k, v in value.items() if k != "submission_id"})[:24] != submission_id:
        raise ValueError("SUBMISSION_CHANGED")
    return value

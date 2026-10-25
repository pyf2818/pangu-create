#!/usr/bin/env python3
"""Skill structural preflight and explicitly executed behavior verification.

python verify_skill.py <skill-dir> [--type output|text] [--json]
python verify_skill.py <skill-dir> --check [--json]
python verify_skill.py <skill-dir> --execute [--suite ID] [--json]

Exit codes: 0 requested checks passed / 1 product or contract failure / 2 usage or
execution environment failure. Default mode is structural only, never a release
certification. --check validates a fresh report; --execute runs trusted local scripts.
"""

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

META_FILES = {".gitkeep", ".ds_store", "readme.md", "index.md"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
WORK_EXTS = {".html", ".htm", ".js", ".mjs", ".py", ".ts", ".tsx", ".jsx",
             ".md", ".json", ".glb", ".gltf", ".mp4", ".webm", ".svg", ".pdf"}
CORE_NAME = re.compile(r"(verify|finalize|build|validate|check|qa|score|inspect)", re.IGNORECASE)
IGNORED_PARTS = {".git", ".omc", "__pycache__", "evidence", "artifacts", "node_modules"}
INJECTION_KINDS = {
    "dependency_unavailable", "extreme_input", "environment_missing",
    "tooling_failure", "invalid_evidence",
}
EVIDENCE_REL = Path("evidence/verification.json")


def section(text, heading):
    match = re.search(rf"^##\s+{re.escape(heading)}.*$", text, re.MULTILINE)
    if not match:
        return ""
    rest = text[match.end():]
    following = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[:following.start()] if following else rest


def real_files(directory):
    if not directory.exists():
        return []
    return [p for p in directory.rglob("*") if p.is_file() and p.name.lower() not in META_FILES]


def normalized_bytes(path):
    # 证据哈希必须跨平台稳定：同一内容在 LF/CRLF 工作树下应得到同一指纹
    return path.read_bytes().replace(b"\r\n", b"\n")


def source_fingerprint(root):
    digest = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file()
                   and not (set(p.relative_to(root).parts) & IGNORED_PARTS)
                   and p.name != "results.tsv")
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big") + relative)
        digest.update(normalized_bytes(path))
    return digest.hexdigest(), len(files)


def contract_path(root):
    return root / "tests" / "verification.json"


def contract_digest(root):
    return hashlib.sha256(normalized_bytes(contract_path(root))).hexdigest()


def load_contract(root):
    path = contract_path(root)
    if not path.exists():
        return [], "缺 tests/verification.json（行为测试清单）"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], f"测试清单不可解析：{exc}"
    if not isinstance(data, dict) or data.get("version") != 1:
        return [], "测试清单 version 必须为 1"
    suites = data.get("suites")
    if not isinstance(suites, list) or not suites:
        return [], "测试清单至少需要一个 suite"
    errors = []
    ids = []
    for index, suite in enumerate(suites):
        label = f"suites[{index}]"
        if not isinstance(suite, dict):
            errors.append(f"{label} 不是对象")
            continue
        suite_id = suite.get("id")
        if not isinstance(suite_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", suite_id):
            errors.append(f"{label} 缺合法 id")
            continue
        if suite_id in ids:
            errors.append(f"重复 suite id：{suite_id}")
        ids.append(suite_id)
        if suite.get("kind") not in {"behavior", "failure_injection"}:
            errors.append(f"{suite_id} kind 必须是 behavior/failure_injection")
        try:
            command = validate_command(root, suite.get("command"))
        except ValueError as exc:
            errors.append(f"{suite_id}：{exc}")
            command = []
        timeout = suite.get("timeout_seconds", 120)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 1 <= timeout <= 600:
            errors.append(f"{suite_id} timeout_seconds 必须为 1-600 秒")
        expected = suite.get("expect", {})
        if not isinstance(expected, dict) or not isinstance(expected.get("exit_code", 0), int):
            errors.append(f"{suite_id} expect.exit_code 必须为整数")
        for key in ("stdout_regex", "stderr_regex"):
            if key in expected:
                try:
                    re.compile(expected[key])
                except (TypeError, re.error):
                    errors.append(f"{suite_id} {key} 不是合法正则")
        categories = suite.get("categories", [])
        if not isinstance(categories, list) or not all(isinstance(item, str) for item in categories):
            errors.append(f"{suite_id} categories 必须是字符串数组")
        elif suite.get("kind") == "failure_injection" and len(set(categories) & INJECTION_KINDS) < 2:
            errors.append(f"{suite_id} 必须声明至少两类实际执行的注入 categories")
        artifacts = suite.get("artifacts", [])
        if not isinstance(artifacts, list):
            errors.append(f"{suite_id} artifacts 必须是数组")
            artifacts = []
        for artifact in artifacts:
            if not isinstance(artifact, str):
                errors.append(f"{suite_id} artifacts 必须是根目录相对路径")
                continue
            try:
                safe_path(root, artifact)
            except ValueError as exc:
                errors.append(f"{suite_id}：{exc}")
    return (suites, "；".join(errors)) if errors else (suites, None)


def safe_path(root, value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("路径为空或非法")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"路径必须在技能目录内：{value}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"路径越过技能目录：{value}")
    return resolved


def validate_command(root, command):
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise ValueError("command 必须是非空字符串数组，不接受 shell 字符串")
    if Path(command[0]).name.lower() not in {"python", "python3", "python.exe"}:
        raise ValueError("仅允许 python 启动受信任的本地测试脚本")
    if any("\x00" in item or re.search(r"[<>|&;\r\n]", item) for item in command):
        raise ValueError("命令包含占位符或 shell 控制字符")
    if any(item.startswith(("/", "\\")) or ".." in Path(item).parts for item in command[1:]):
        raise ValueError("命令参数不得指向技能目录之外")
    if command[1:2] == ["-m"]:
        if command[2:3] != ["unittest"]:
            raise ValueError("Python 模块仅允许标准库 unittest")
        return command
    scripts = [item for item in command[1:] if item.endswith(".py")]
    if len(scripts) != 1:
        raise ValueError("命令必须指定一个技能目录内的 .py 测试脚本")
    path = safe_path(root, scripts[0])
    if not path.is_file():
        raise ValueError(f"测试脚本不存在：{scripts[0]}")
    return command


def promise_rows(root):
    path = root / "references" / "promise-table.md"
    if not path.exists():
        return [], "缺 references/promise-table.md"
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell):
            continue
        if "承诺" in cells[0] or cells[0] in {"#", ""}:
            continue
        rows.append(cells)
    return rows, None


def gate_promise(root):
    rows, error = promise_rows(root)
    if error:
        return False, error
    suites, error = load_contract(root)
    if error:
        return False, error
    ids = {suite["id"] for suite in suites}
    issues = []
    for cells in rows:
        label = cells[0][:24]
        if len(cells) < 4:
            issues.append(f"「{label}」少于四列")
            continue
        match = re.fullmatch(r"`?([a-z0-9][a-z0-9-]*)`?", cells[2])
        if not match or match.group(1) not in ids:
            issues.append(f"「{label}」第三列须引用清单中的测试 ID")
        evidence = cells[3].strip("` ")
        if evidence != f"{EVIDENCE_REL.as_posix()}#{cells[2].strip('`')}":
            issues.append(f"「{label}」证据须指向当前回执的同一测试 ID")
        if any(re.search(r"TODO|待填|已测试|验证通过", cell) for cell in cells):
            issues.append(f"「{label}」含占位或自述性证据")
    if len(rows) < 3:
        issues.append(f"承诺矩阵 {len(rows)} 行（需 ≥3）")
    return not issues, "；".join(issues[:5]) if issues else f"{len(rows)} 条承诺均绑定测试 ID 与回执"


def gate_thesis(root):
    path = root / "references" / "design-thesis.md"
    if not path.exists():
        return False, "缺 references/design-thesis.md（论点档案）"
    text = path.read_text(encoding="utf-8", errors="replace")
    issues = []
    if "TODO" in text:
        issues.append("仍有 TODO 未填")
    answers = [a.strip() for a in re.findall(r"^\|\s*[^|]+\|\s*([^|]+)\|", section(text, "三问"), re.M)]
    answers = [a for a in answers if a and not re.fullmatch(r"-{2,}", a) and a != "回答"]
    if len(answers) < 3:
        issues.append(f"三问只填了 {len(answers)} 条")
    competition = section(text, "竞争测试")
    if not competition or "TODO" in competition:
        issues.append("竞争测试材料未完成")
    elif not re.search(r"不成立|不通过|只有本|说不出", competition):
        issues.append("竞争测试未给出明确结论；语义仍需独立评审")
    materials = re.findall(r"^\|\s*\d+\s*\|", section(text, "独有素材") or text, re.MULTILINE)
    if len(materials) < 8:
        issues.append(f"独有素材 {len(materials)} 条（需 ≥8）")
    return not issues, "；".join(issues) if issues else "论点材料齐全；原创性与竞争结论需独立评审"


def gate_examples(root):
    files = [p for directory in (root / "examples", root / "assets" / "examples") for p in real_files(directory)]
    works = [p for p in files if p.suffix.lower() in WORK_EXTS]
    return len(works) >= 3, f"可打开范例 {len(works)} 件（需 ≥3）"


def gate_signature(root):
    files = [p for directory in (root / "assets" / "showcase", root / "showcase") for p in real_files(directory)]
    works = [p for p in files if p.suffix.lower() in WORK_EXTS]
    if not files:
        return False, "缺 assets/showcase/（署名作品）"
    return bool(works), "署名作品材料存在" if works else "只有截图，没有可打开的作品文件"


def gate_core(root):
    scripts = [p for p in real_files(root / "scripts") if p.suffix.lower() in {".py", ".mjs", ".js", ".sh", ".ts"}]
    core = [p for p in scripts if CORE_NAME.search(p.stem)]
    return bool(core), "发现验收/构建入口；实际行为由 --execute 验证" if core else "缺一键验收/构建脚本"


def gate_contract(root):
    suites, error = load_contract(root)
    if error:
        return False, error
    failure = [suite for suite in suites if suite["kind"] == "failure_injection"]
    if not failure:
        return False, "清单没有 failure_injection suite"
    categories = sorted({category for suite in failure for category in suite["categories"]})
    return True, f"{len(suites)} 个测试套件可执行；注入类别：{', '.join(categories)}"


def run_suite(root, suite):
    started = datetime.now(timezone.utc)
    command = [sys.executable, *suite["command"][1:]]
    expected = suite.get("expect", {})
    result = {"id": suite["id"], "kind": suite["kind"], "command": suite["command"],
              "started_at": started.isoformat(), "status": "fail"}
    try:
        process = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace",
                                 timeout=suite.get("timeout_seconds", 120), shell=False)
        stdout, stderr = process.stdout, process.stderr
        result.update({"exit_code": process.returncode, "stdout": stdout[-24000:], "stderr": stderr[-24000:]})
        expected_exit = expected.get("exit_code", 0)
        reasons = []
        if process.returncode != expected_exit:
            reasons.append(f"exit={process.returncode}，期望 {expected_exit}")
        for key, stream in (("stdout_regex", stdout), ("stderr_regex", stderr)):
            if key in expected and not re.search(expected[key], stream, re.MULTILINE):
                reasons.append(f"{key} 未匹配")
        result["status"] = "pass" if not reasons else ("env_error" if process.returncode == 2 and expected_exit != 2 else "fail")
        result["failures"] = reasons
    except subprocess.TimeoutExpired as exc:
        result.update({"status": "fail", "failures": [f"超过 {exc.timeout} 秒"]})
    except OSError as exc:
        result.update({"status": "env_error", "failures": [str(exc)]})
    artifacts = []
    for value in suite.get("artifacts", []):
        path = safe_path(root, value)
        item = {"path": value, "exists": path.is_file()}
        if item["exists"]:
            item["bytes"] = path.stat().st_size
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            result["status"] = "fail"
            result.setdefault("failures", []).append(f"缺证据文件：{value}")
        artifacts.append(item)
    result["artifacts"] = artifacts
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


def execute_contract(root, selected=None):
    suites, error = load_contract(root)
    if error:
        raise ValueError(error)
    unknown = set(selected or []) - {suite["id"] for suite in suites}
    if unknown:
        raise ValueError(f"未知测试 ID：{', '.join(sorted(unknown))}")
    chosen = [suite for suite in suites if not selected or suite["id"] in selected]
    results = [run_suite(root, suite) for suite in chosen]
    overall = 2 if any(result["status"] == "env_error" for result in results) else int(any(result["status"] != "pass" for result in results))
    fingerprint, file_count = source_fingerprint(root)
    return {
        "format_version": 1,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "skill": root.name,
        "complete": not selected,
        "suite_ids": [suite["id"] for suite in chosen],
        "source_file_count": file_count,
        "source_sha256": fingerprint,
        "contract_sha256": contract_digest(root),
        "overall_exit_code": overall,
        "status": {0: "pass", 1: "fail", 2: "env_error"}[overall],
        "suites": results,
    }


def gate_evidence(root):
    path = root / EVIDENCE_REL
    if not path.is_file():
        return False, f"缺 {EVIDENCE_REL.as_posix()}；须用 --execute 真实运行"
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        fingerprint, _ = source_fingerprint(root)
        contract_hash = contract_digest(root)
        suites, error = load_contract(root)
        if error:
            return False, error
        declared = {suite["id"] for suite in suites}
        issues = []
        if report.get("format_version") != 1 or not report.get("executed_at"):
            issues.append("回执版本或执行时间缺失")
        if not report.get("complete") or set(report.get("suite_ids", [])) != declared:
            issues.append("回执没有完整覆盖当前测试清单")
        if report.get("source_sha256") != fingerprint:
            issues.append("源码或产物已变化，回执过期")
        if report.get("contract_sha256") != contract_hash:
            issues.append("测试清单已变化，回执过期")
        if report.get("status") != "pass" or report.get("overall_exit_code") != 0:
            issues.append("回执不是全部通过")
        suites_report = report.get("suites")
        if not isinstance(suites_report, list) or not suites_report:
            issues.append("回执不含套件结果")
        else:
            reported = [suite.get("id") for suite in suites_report if isinstance(suite, dict)]
            if len(reported) != len(set(reported)) or set(reported) != declared:
                issues.append("回执套件与当前清单不一致")
            if any(suite.get("status") != "pass" for suite in suites_report if isinstance(suite, dict)):
                issues.append("回执含未通过套件")
        return not issues, "；".join(issues) if issues else f"当前源码的完整行为回执有效（{len(suites_report)} 套件）"
    except (OSError, ValueError, TypeError) as exc:
        return False, f"回执不可解析：{exc}"


def gate_trio(root):
    issues = []
    if not (root / "test-prompts.json").exists():
        issues.append("缺 test-prompts.json")
    if not (root / "results.tsv").exists():
        issues.append("缺 results.tsv")
    if not (root / ".git").exists() and not list(root.glob("*.bak.*")):
        issues.append("缺 git 或备份链")
    return not issues, "；".join(issues) if issues else "进化三件套齐备"


def main():
    parser = argparse.ArgumentParser(description="结构预检 / 回执核验 / 显式行为验收")
    parser.add_argument("skill_dir")
    parser.add_argument("--type", choices=["output", "text"], default="output")
    parser.add_argument("--json", action="store_true", help="stdout 只输出 JSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="执行 tests/verification.json 中受信任的本地脚本")
    mode.add_argument("--check", action="store_true", help="不执行，核验当前源码的最新完整回执")
    parser.add_argument("--suite", action="append", help="仅调试指定测试 ID；不能作为交付回执")
    args = parser.parse_args()
    root = Path(args.skill_dir).resolve()
    if not root.is_dir() or not (root / "SKILL.md").is_file():
        print(f"FATAL: 不是含 SKILL.md 的技能目录：{root}", file=sys.stderr)
        sys.exit(2)
    if args.suite and not args.execute:
        parser.error("--suite 只能与 --execute 一起使用")

    gates = [("SKILL.md", True, "入口存在"),
             ("确定性入口", *gate_core(root)),
             ("测试与故障清单", *gate_contract(root)),
             ("承诺绑定", *gate_promise(root))]
    if args.type == "output":
        gates[1:1] = [("论点材料", *gate_thesis(root)),
                      ("范例材料", *gate_examples(root)),
                      ("署名作品", *gate_signature(root))]
    else:
        gates.append(("进化三件套", *gate_trio(root)))
    structural_pass = all(item[1] for item in gates)
    output = {"skill": root.name, "type": args.type,
              "mode": "behavior" if args.execute else "evidence" if args.check else "structure",
              "delivery_ready": False, "gates": []}
    exit_code = 0 if structural_pass else 1
    if args.execute:
        try:
            report = execute_contract(root, args.suite)
            exit_code = max(exit_code, report["overall_exit_code"])
            report_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            if args.suite:
                report_path = root / "evidence" / f"partial-{report['suite_ids'][0]}.json"
                output["mode"] = "partial"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(report_text, encoding="utf-8")
                output["evidence_report"] = report_path.relative_to(root).as_posix()
            elif structural_pass:
                report_path = root / EVIDENCE_REL
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(report_text, encoding="utf-8")
                output["evidence_report"] = report_path.relative_to(root).as_posix()
                passed, detail = gate_evidence(root)
                gates.append(("当前行为回执", passed, detail))
                if not passed:
                    exit_code = max(exit_code, 1)
            else:
                output["execution_results"] = report["suites"]
            output["behavior_summary"] = {"pass": sum(r["status"] == "pass" for r in report["suites"]),
                                         "total": len(report["suites"]),
                                         "environment_failure": report["overall_exit_code"] == 2}
        except (ValueError, OSError) as exc:
            gates.append(("行为执行", False, str(exc)))
            exit_code = max(exit_code, 1)
    elif args.check:
        passed, detail = gate_evidence(root)
        gates.append(("当前行为回执", passed, detail))
        if not passed:
            exit_code = max(exit_code, 1)
            try:
                saved = json.loads((root / EVIDENCE_REL).read_text(encoding="utf-8"))
                if saved.get("overall_exit_code") == 2:
                    exit_code = 2
            except (OSError, ValueError, TypeError):
                pass
    output["pass"] = exit_code == 0
    output["delivery_ready"] = exit_code == 0 and output["mode"] in {"behavior", "evidence"} and not args.suite
    output["gates"] = [{"name": name, "pass": passed, "detail": detail} for name, passed, detail in gates]
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"模式: {output['mode']}（{root.name}，type={args.type}）")
        for name, passed, detail in gates:
            print(f"  {'PASS' if passed else 'FAIL'}  {name}  {detail}")
        if "behavior_summary" in output:
            summary = output["behavior_summary"]
            print(f"行为验收: {summary['pass']}/{summary['total']} PASS")
        if output["delivery_ready"]:
            print(f"声明测试与当前回执通过：{EVIDENCE_REL.as_posix()}；仍需独立效果评审。")
        elif args.suite:
            print("仅部分测试，不能作为交付验收。")
        elif output["mode"] == "structure" and structural_pass:
            print("仅结构预检完成；未执行行为测试，不能据此宣称发布级。")
        else:
            print("存在未通过项；环境故障 exit 2，产品/清单失败 exit 1。")
    sys.exit(exit_code)


if __name__ == "__main__":
    sys.exit(main())

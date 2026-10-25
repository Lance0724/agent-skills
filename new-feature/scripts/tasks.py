#!/usr/bin/env python3
"""以 tasks.json 为唯一状态源管理新功能流程；仅使用 Python 标准库。"""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sys
import tempfile


PHASES = ("requirements", "specification", "planning", "execution", "completed")
STATUSES = ("pending", "in_progress", "blocked", "completed", "skipped")
TASK_FIELDS = {"id", "title", "design_refs", "acceptance_refs", "depends_on", "scope",
               "completion_criteria", "verification_plan", "status", "reason", "verification"}
STATE_FIELDS = {"schema_version", "workflow", "mode", "mode_history", "phase", "revision",
                "acceptance_ids", "design_ids", "gates", "blocker", "tasks"}


class StateError(Exception):
    """可直接向调用者解释的输入或状态错误。"""


def require(condition, message):
    if not condition:
        raise StateError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, nonempty=False):
    return (isinstance(value, list) and (not nonempty or bool(value))
            and all(text(item) for item in value) and len(set(value)) == len(value))


def identifiers(value, prefix, nonempty=False):
    return strings(value, nonempty) and all(re.fullmatch(prefix + r"-[0-9]{3,}", item) for item in value)


def covered(state, verified=False):
    tasks = state["tasks"]
    if verified:
        tasks = [t for t in tasks if t["status"] == "completed"]
    for field, registry in (("acceptance_refs", "acceptance_ids"), ("design_refs", "design_ids")):
        present = {ref for task in tasks for ref in task[field]}
        missing = set(state[registry]) - present
        require(not missing, f"未覆盖的 {registry}：{', '.join(sorted(missing))}")


def validate(state):
    require(isinstance(state, dict) and set(state) == STATE_FIELDS, "tasks.json 顶层字段不完整或含未知字段")
    require(type(state["schema_version"]) is int and state["schema_version"] == 1, "不支持的 schema_version")
    require(state["workflow"] == "new-feature", "workflow 必须为 new-feature")
    require(state["mode"] in ("lightweight", "standard"), "无效的 mode")
    require(state["phase"] in PHASES, "无效的 phase")
    require(type(state["revision"]) is int and state["revision"] >= 0, "revision 必须为非负整数")
    require(state["blocker"] is None or text(state["blocker"]), "blocker 必须为空或非空原因")
    history = state["mode_history"]
    require(isinstance(history, list) and bool(history), "缺少模式选择依据")
    for item in history:
        require(isinstance(item, dict) and set(item) == {"mode", "reason"}
                and item["mode"] in ("lightweight", "standard") and text(item["reason"]), "无效的模式记录")
    require(history[-1]["mode"] == state["mode"], "模式与最后一次选择记录不一致")
    require(identifiers(state["acceptance_ids"], "AC"), "acceptance_ids 必须为唯一 AC-编号列表")
    require(identifiers(state["design_ids"], "DES"), "design_ids 必须为唯一 DES-编号列表")
    index = PHASES.index(state["phase"])
    require(isinstance(state["gates"], dict) and set(state["gates"]) == set(PHASES[:index]), "阶段门槛记录与当前阶段不一致")
    require(all(text(reason) for reason in state["gates"].values()), "阶段门槛必须有依据")
    require(index == 0 or state["acceptance_ids"], "需求阶段完成后必须登记验收标准")
    require(index < 2 or state["design_ids"], "规范阶段完成后必须登记设计编号")
    require(isinstance(state["tasks"], list), "tasks 必须为列表")
    tasks = {}
    for task in state["tasks"]:
        require(isinstance(task, dict) and set(task) == TASK_FIELDS, "任务字段不完整或含未知字段")
        require(identifiers([task["id"]], "TASK"), "无效的 TASK-编号")
        require(task["id"] not in tasks, f"重复任务：{task['id']}")
        tasks[task["id"]] = task
        for field in ("title", "completion_criteria", "verification_plan"):
            require(text(task[field]), f"{task['id']} 缺少 {field}")
        require(strings(task["scope"], True), "scope 必须为非空字符串列表")
        for field, prefix, registry in (("design_refs", "DES", "design_ids"), ("acceptance_refs", "AC", "acceptance_ids")):
            require(identifiers(task[field], prefix, True), f"无效的 {field}")
            require(set(task[field]) <= set(state[registry]), f"{field} 包含未登记编号")
        require(identifiers(task["depends_on"], "TASK"), "无效的 depends_on")
        require(task["status"] in STATUSES, "无效的任务状态")
        require(task["reason"] is None or text(task["reason"]), "reason 必须为空或非空字符串")
        if task["status"] in ("blocked", "skipped"):
            require(text(task["reason"]), "阻塞或跳过任务必须说明原因")
        check = task["verification"]
        require(isinstance(check, dict) and set(check) == {"result", "command", "observed", "evidence_refs"}, "无效的 verification 字段")
        require(check["result"] in ("not_run", "passed", "failed"), "无效的验证结果")
        require(strings(check["evidence_refs"]), "evidence_refs 必须为唯一字符串列表")
        if check["result"] == "not_run":
            require(check["command"] is None and check["observed"] is None and not check["evidence_refs"], "未运行验证不得附带结果")
        else:
            require(text(check["command"]) and text(check["observed"]), "验证结果必须包含实际命令或场景和观察结果")
        if task["status"] == "completed":
            require(check["result"] == "passed", "任务完成前必须有通过的验证结果")
        if task["status"] in ("pending", "skipped"):
            require(check["result"] == "not_run", "待处理或跳过任务不得复用旧验证")
    require(index >= 2 or not tasks, "计划阶段前不得添加任务")
    for task in tasks.values():
        require(set(task["depends_on"]) <= tasks.keys(), f"{task['id']} 依赖不存在的任务")
        if task["status"] in ("in_progress", "completed"):
            require(all(tasks[dep]["status"] == "completed" for dep in task["depends_on"]), f"{task['id']} 的依赖尚未完成；跳过不等于满足依赖")
        if index < 3:
            require(task["status"] in ("pending", "blocked", "skipped"), "执行阶段前不得开始任务")
    visiting, visited = set(), set()

    def visit(task_id):
        require(task_id not in visiting, "任务依赖存在环")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dep in tasks[task_id]["depends_on"]:
            visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)
    if index >= 3:
        require(bool(tasks), "执行阶段必须有任务")
        covered(state)
    if state["phase"] == "completed":
        require(state["blocker"] is None, "流程仍有阻塞")
        require(all(t["status"] in ("completed", "skipped") for t in tasks.values()), "仍有未结束任务")
        covered(state, verified=True)


def empty_verification():
    return {"result": "not_run", "command": None, "observed": None, "evidence_refs": []}


def load(path):
    require(not path.is_symlink(), "拒绝读写符号链接 tasks.json")
    with path.open(encoding="utf-8") as stream:
        state = json.load(stream)
    validate(state)
    return state


@contextmanager
def writer_lock(directory):
    # 单写入者策略外，再用排他文件防止意外同时写入。
    path = directory / ".tasks.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise StateError("存在 .tasks.lock；另一更新可能正在进行。确认原进程退出后才能移除遗留锁。") from None
    try:
        os.close(descriptor)
        yield
    finally:
        path.unlink()


def save(path, state):
    validate(state)
    require(not path.is_symlink(), "拒绝写入符号链接 tasks.json")
    # 同目录原子替换让读者只看到完整的新旧版本，不留下半截 JSON。
    descriptor, temporary = tempfile.mkstemp(prefix=".tasks-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def definitions(args):
    return {
        "title": args.title, "design_refs": args.design, "acceptance_refs": args.acceptance,
        "depends_on": args.depends, "scope": args.scope,
        "completion_criteria": args.done_when, "verification_plan": args.verify,
    }


def change(state, args, directory):
    command = args.command
    if command == "hold":
        require(state["phase"] != "completed", "流程已完成；先重新打开任务")
        require(state["blocker"] is None and text(args.reason), "已阻塞或缺少阻塞原因")
        state["blocker"] = args.reason
        return
    if command == "resume":
        require(state["blocker"] is not None, "流程未阻塞")
        state["blocker"] = None
        return
    if command == "replan":
        require(state["phase"] in ("planning", "execution", "completed"), "仅计划阶段后可以重新规划")
        require(text(args.reason), "重新规划必须说明原因")
        if args.acceptance is not None:
            state["acceptance_ids"] = args.acceptance
        if args.design is not None:
            state["design_ids"] = args.design
        state["phase"] = "planning"
        state["gates"] = {"requirements": args.reason, "specification": args.reason}
        for task in state["tasks"]:
            task["status"], task["reason"] = "pending", args.reason
            task["verification"] = empty_verification()
        return
    if command == "mode":
        require(text(args.reason), "切换模式必须说明原因")
        require(args.mode != state["mode"], "已经处于指定模式")
        if args.mode == "lightweight":
            require(state["phase"] in PHASES[:3], "执行开始后不可降为轻量模式")
        state["mode"] = args.mode
        state["mode_history"].append({"mode": args.mode, "reason": args.reason})
        return
    if command == "advance":
        phase = state["phase"]
        require(phase != "completed", "流程已完成")
        require(text(args.reason), "阶段推进必须记录门槛依据")
        require(state["blocker"] is None, "流程有阻塞，先解决问题并 resume")
        if phase == "requirements":
            require((directory / "requirements.md").is_file(), "缺少 requirements.md")
            require(identifiers(args.acceptance, "AC", True), "请用 --acceptance 登记全部验收编号")
            require(args.design is None, "需求阶段不能登记设计编号")
            state["acceptance_ids"] = args.acceptance
        elif phase == "specification":
            require((directory / "specification.md").is_file(), "缺少 specification.md")
            require(identifiers(args.design, "DES", True), "请用 --design 登记全部设计编号")
            require(args.acceptance is None, "当前阶段不能重新登记验收编号")
            state["design_ids"] = args.design
        else:
            require(args.acceptance is None and args.design is None, "当前阶段不接受编号登记")
        state["gates"][phase] = args.reason
        state["phase"] = PHASES[PHASES.index(phase) + 1]
        return
    if command == "add":
        require(state["phase"] in ("planning", "execution"), "仅在计划或执行阶段添加任务")
        require(all(t["id"] != args.id for t in state["tasks"]), "任务编号已存在")
        state["tasks"].append({"id": args.id, **definitions(args), "status": "pending",
                               "reason": None, "verification": empty_verification()})
        return
    task = next((t for t in state["tasks"] if t["id"] == args.id), None)
    require(task is not None, f"任务不存在：{args.id}")
    status = task["status"]
    if command == "update":
        require(status == "pending", "仅可修改待处理任务；已开始任务先 reopen")
        updates = {key: value for key, value in definitions(args).items() if value is not None}
        require(bool(updates), "未提供要更新的字段")
        task.update(updates)
    elif command == "start":
        require(state["phase"] == "execution", "仅执行阶段可开始任务")
        require(state["blocker"] is None, "流程有阻塞，不能开始任务")
        require(status == "pending", "只能开始 pending 任务；blocked 任务先 unblock")
        task["status"], task["reason"] = "in_progress", None
    elif command == "block":
        require(status in ("pending", "in_progress"), "只能阻塞待处理或进行中的任务")
        require(text(args.reason), "阻塞必须说明原因和解除条件")
        task["status"], task["reason"] = "blocked", args.reason
        task["verification"] = empty_verification()
    elif command == "unblock":
        require(status == "blocked", "只能解除 blocked 任务")
        task["status"], task["reason"] = "pending", None
    elif command == "verify":
        require(status == "in_progress", "只能验证进行中的任务")
        task["verification"] = {"result": args.result, "command": args.check,
                                "observed": args.observed, "evidence_refs": args.evidence}
    elif command == "complete":
        require(status == "in_progress", "只能完成进行中的任务")
        require(task["verification"]["result"] == "passed", "请先 verify 记录真实通过结果")
        task["status"] = "completed"
    elif command == "skip":
        require(status in ("pending", "blocked"), "仅可跳过待处理或阻塞任务；进行中任务先 reopen")
        require(text(args.reason), "不适用任务必须说明原因")
        task["status"], task["reason"] = "skipped", args.reason
        task["verification"] = empty_verification()
    elif command == "reopen":
        require(status != "pending", "任务已经待处理")
        require(text(args.reason), "重新打开必须说明原因")
        affected = {task["id"]}
        while True:
            expanded = affected | {t["id"] for t in state["tasks"] if set(t["depends_on"]) & affected}
            if expanded == affected:
                break
            affected = expanded
        for item in state["tasks"]:
            if item["id"] in affected:
                item["status"] = "pending"
                item["reason"] = f"重新评估 {task['id']}：{args.reason}"
                item["verification"] = empty_verification()
        if state["phase"] == "completed":
            state["phase"] = "execution"
            del state["gates"]["execution"]


def _render_text(state, directory):
    """从已校验的状态生成只读视图，不读取证据或执行验证。"""
    status_labels = {"completed": "已完成", "in_progress": "进行中", "pending": "待处理",
                     "blocked": "已阻塞", "skipped": "已跳过"}
    phase_labels = {"requirements": "需求", "specification": "规范", "planning": "计划",
                    "execution": "执行中", "completed": "已完成"}
    mode_labels = {"lightweight": "轻量", "standard": "标准"}
    result_labels = {"not_run": "未运行", "passed": "通过", "failed": "失败，需修复后重新验证"}
    tasks = state["tasks"]
    by_id = {task["id"]: task for task in tasks}
    counts = dict.fromkeys(status_labels, 0)
    completed_refs = {"acceptance_refs": set(), "design_refs": set()}
    for task in tasks:
        counts[task["status"]] += 1
        if task["status"] == "completed":
            for field in completed_refs:
                completed_refs[field].update(task[field])
    missing = {}
    for label, field, registry in (("验收", "acceptance_refs", "acceptance_ids"),
                                   ("设计", "design_refs", "design_ids")):
        missing[label] = [ref for ref in state[registry] if ref not in completed_refs[field]]
    waiting = {task["id"]: [dep for dep in task["depends_on"] if by_id[dep]["status"] != "completed"]
               for task in tasks}
    phase, mode = state["phase"], state["mode"]
    unfinished = counts["pending"] + counts["in_progress"] + counts["blocked"]
    can_finish = (phase == "execution" and not state["blocker"] and not unfinished
                  and not any(missing.values()))
    lines = []

    def field(label, value, indent=""):
        parts = str(value).splitlines() or [""]
        lines.append(f"{indent}{label}：{parts[0]}")
        lines.extend(f"{indent}  {part}" for part in parts[1:])

    field("功能", directory.absolute().name)
    field("目录", directory)
    lines.append("")
    field("阶段", f"{phase_labels[phase]}（{phase}）")
    field("模式", f"{mode_labels[mode]}（{mode}）")
    field("版本", state["revision"])
    field("流程阻塞", state["blocker"] or "无")
    lines.extend(["", "任务概况"])
    summary = " · ".join(f"{label} {counts[status]}" for status, label in status_labels.items())
    lines.append(f"  总计 {len(tasks)} 项：{summary}")
    for label, registry in (("验收", "acceptance_ids"), ("设计", "design_ids")):
        total = len(state[registry])
        coverage = f"已完成任务覆盖 {total - len(missing[label])}/{total} 项" if total else "尚未登记"
        field(f"{label}覆盖", coverage, "  ")
    lines.extend(["", "任务列表"])
    if not tasks:
        lines.append("  暂无任务")
    for index, task in enumerate(tasks):
        if index:
            lines.append("")
        task_id, status = task["id"], task["status"]
        title = " ".join(task["title"].splitlines())
        lines.append(f"  {task_id}  {status_labels[status]}  {title}")
        dependencies = "、".join(f"{dep}（{status_labels[by_id[dep]['status']]}）" for dep in task["depends_on"])
        field("依赖", dependencies or "无", "            ")
        field("验证", result_labels[task["verification"]["result"]], "            ")
        if status == "pending":
            constraints = []
            if state["blocker"]:
                constraints.append("流程阻塞尚未解除")
            if phase != "execution":
                constraints.append("尚未进入执行阶段")
            if waiting[task_id]:
                constraints.append("依赖尚未完成：" + "、".join(waiting[task_id]) + "（跳过不满足依赖）")
            field("启动条件", "；".join(constraints) if constraints else "已满足，可开始", "            ")
        if status in ("blocked", "skipped"):
            field("阻塞原因" if status == "blocked" else "跳过原因", task["reason"], "            ")

    lines.extend(["", "需要关注"])
    concerns = False
    if state["blocker"]:
        field("流程阻塞", state["blocker"], "  ")
        concerns = True
    for task in tasks:
        check = task["verification"]
        if check["result"] == "failed":
            lines.append(f"  {task['id']} · 最近验证失败")
            field("执行", check["command"], "    ")
            field("观察", check["observed"], "    ")
            field("证据", "、".join(check["evidence_refs"]) or "未附加引用", "    ")
            concerns = True
        if task["status"] == "blocked":
            lines.append(f"  {task['id']} · 任务阻塞")
            field("原因", task["reason"], "    ")
            concerns = True
    for label, refs in missing.items():
        if refs:
            field(f"尚未被已完成任务覆盖的{label}", "、".join(refs), "  ")
            concerns = True
    if not concerns:
        lines.append("  无失败验证、阻塞或已登记编号的完成覆盖缺口")

    steps = []
    if state["blocker"]:
        steps.append("先按记录条件解决流程阻塞并 resume；解除前不开始新任务或推进阶段。")
    elif phase == "requirements":
        steps.append("完善 requirements.md，审查需求门槛后用 advance 登记全部验收编号。")
    elif phase == "specification":
        steps.append("完善 specification.md，审查规范门槛后用 advance 登记全部设计编号。")
    elif phase == "planning":
        steps.append("审查任务覆盖、依赖及验证计划；计划门槛满足后用 advance 进入执行阶段。")
    elif phase == "completed":
        steps.append("流程已完成，无待执行任务。")
    else:
        for task in tasks:
            task_id, status = task["id"], task["status"]
            if status == "in_progress":
                result = task["verification"]["result"]
                if result == "failed":
                    steps.append(f"修复 {task_id}，重新验证通过后完成任务。")
                elif result == "passed":
                    steps.append(f"{task_id} 已记录通过验证；确认实现未再变动后可 complete。")
                else:
                    steps.append(f"继续实施 {task_id} 并实际验证，记录结果后再完成任务。")
            elif status == "blocked":
                steps.append(f"按记录条件解除 {task_id} 的阻塞；unblock 后仍需检查依赖再 start。")
            elif status == "pending":
                dependencies = waiting[task_id]
                if any(by_id[dep]["status"] == "skipped" for dep in dependencies):
                    steps.append(f"{task_id} 有已跳过的依赖，不满足启动条件；先重新评估依赖计划。")
                elif dependencies:
                    steps.append(f"等待 {'、'.join(dependencies)} 完成后，再开始 {task_id}。")
                else:
                    steps.append(f"可开始 {task_id}。")
        if can_finish:
            steps.append("状态门槛已满足；人工确认实际验收和文档一致后，用 advance 完成流程。")
        elif not unfinished and any(missing.values()):
            steps.append("仍有完成覆盖缺口；重新评估相关跳过任务或补充任务并实际验证。")
    lines.extend(["", "下一步"])
    lines.extend(f"  {index}. {step}" for index, step in enumerate(steps, 1))
    lines.append("")
    if phase == "completed":
        field("完成判定", "已完成（按已记录状态）")
    elif can_finish:
        field("完成判定", "状态门槛已满足，待人工确认并推进阶段")
    else:
        field("完成判定", "尚未满足")
        if phase != "execution":
            lines.append("  尚未进入执行阶段。")
        if state["blocker"]:
            lines.append("  流程阻塞尚未解除。")
        if unfinished:
            lines.append(f"  仍有 {unfinished} 项任务未结束。")
        if any(missing.values()):
            lines.append("  部分验收或设计尚未被已完成任务覆盖。")
    lines.extend(["", "说明：覆盖仅按已完成任务的编号关联计算，不代表脚本已判断产品行为正确。"])
    return "\n".join(lines)


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    for name in ("init", "show", "validate", "add", "update", "start", "block", "unblock",
                 "verify", "complete", "skip", "reopen", "advance", "mode", "hold", "resume", "replan"):
        command = commands.add_parser(name)
        command.add_argument("directory", type=Path, help="功能产物目录，不是技能目录")
        if name == "show":
            command.add_argument("--format", choices=("json", "text"), default="json",
                                 help="输出格式：json 完整状态（默认），text 本地只读摘要")
        if name not in ("init", "show", "validate"):
            command.add_argument("--expect-revision", type=int, help="拒绝基于过期版本更新")
        if name in ("init", "mode"):
            command.add_argument("--mode", choices=("lightweight", "standard"), required=True)
        if name in ("init", "mode", "block", "skip", "reopen", "advance", "hold", "replan"):
            command.add_argument("--reason", required=True)
        if name in ("add", "update", "start", "block", "unblock", "verify", "complete", "skip", "reopen"):
            command.add_argument("id", help="例如 TASK-001")
        if name in ("add", "update"):
            required = name == "add"
            command.add_argument("--title", required=required)
            command.add_argument("--design", nargs="+", required=required)
            command.add_argument("--acceptance", nargs="+", required=required)
            command.add_argument("--depends", nargs="*", default=[] if required else None)
            command.add_argument("--scope", nargs="+", required=required)
            command.add_argument("--done-when", required=required)
            command.add_argument("--verify", required=required, help="计划运行的命令或场景，不会执行")
        if name in ("advance", "replan"):
            command.add_argument("--acceptance", nargs="+")
            command.add_argument("--design", nargs="+")
        if name == "verify":
            command.add_argument("--result", choices=("passed", "failed"), required=True)
            command.add_argument("--check", required=True, help="实际执行的命令或场景；仅记录，不执行")
            command.add_argument("--observed", required=True)
            command.add_argument("--evidence", nargs="*", default=[])
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        directory = args.directory.absolute()
        require(not any(p.is_symlink() for p in (directory, *directory.parents)), "功能目录不能包含符号链接")
        if args.command == "init":
            require(text(args.reason), "初始化必须记录模式依据")
            directory.mkdir(parents=True, exist_ok=True)
        require(directory.is_dir(), "功能目录不存在；先执行 init")
        path = directory / "tasks.json"
        if args.command in ("show", "validate"):
            state = load(path)
        else:
            with writer_lock(directory):
                if args.command == "init":
                    require(not path.exists() and not path.is_symlink(), "tasks.json 已存在，拒绝覆盖")
                    state = {"schema_version": 1, "workflow": "new-feature", "mode": args.mode,
                             "mode_history": [{"mode": args.mode, "reason": args.reason}],
                             "phase": "requirements", "revision": 0, "acceptance_ids": [],
                             "design_ids": [], "gates": {}, "blocker": None, "tasks": []}
                else:
                    state = load(path)
                    require(args.expect_revision is None or state["revision"] == args.expect_revision,
                            "revision 已变化；先 show 读取最新状态")
                    change(state, args, directory)
                    state["revision"] += 1
                save(path, state)
        if args.command == "show" and args.format == "text":
            print(_render_text(state, args.directory))
            return 0
        output = state if args.command == "show" else {
            "ok": True, "phase": state["phase"], "mode": state["mode"],
            "revision": state["revision"], "task_count": len(state["tasks"]),
        }
        if hasattr(args, "id"):
            output["task"] = next({"id": t["id"], "status": t["status"]}
                                  for t in state["tasks"] if t["id"] == args.id)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (StateError, OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

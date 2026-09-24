"""验证调用者可观察到的状态转换、覆盖约束及失败时的文件保护。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).with_name("tasks.py")


class TaskLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "中文 feature"
        self.directory.mkdir()
        self.path = self.directory / "tasks.json"
        self.call("init", "--mode", "lightweight", "--reason", "单模块，无持久化和安全边界变化")

    def call(self, command, *arguments):
        result = subprocess.run([sys.executable, str(CLI), command, str(self.directory), *arguments],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def rejected(self, command, *arguments):
        before = self.path.read_bytes()
        result = subprocess.run([sys.executable, str(CLI), command, str(self.directory), *arguments],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.path.read_bytes(), before)

    def state(self):
        return self.call("show")

    def planning(self, acceptance=("AC-001",), designs=("DES-001",)):
        (self.directory / "requirements.md").write_text("# 需求\n拒绝非法输入。\n", encoding="utf-8")
        self.call("advance", "--acceptance", *acceptance, "--reason", "需求已经审查")
        (self.directory / "specification.md").write_text("# 规范\n复用校验入口。\n", encoding="utf-8")
        self.call("advance", "--design", *designs, "--reason", "设计已经审查")

    def add(self, task="TASK-001", acceptance="AC-001", design="DES-001", depends=()):
        self.call("add", task, "--title", "校验输入", "--acceptance", acceptance,
                  "--design", design, "--scope", "src/input.py", "--done-when", "非法输入被拒绝",
                  "--verify", "运行输入校验场景", "--depends", *depends)

    def finish(self, task):
        self.call("start", task)
        self.call("verify", task, "--result", "passed", "--check", "校验场景",
                  "--observed", "非法输入被拒绝，合法输入正常")
        self.call("complete", task)

    def show_text(self):
        result = subprocess.run([sys.executable, str(CLI), "show", str(self.directory),
                                 "--format", "text"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_text_view_is_deterministic_readonly_and_preserves_json(self):
        self.planning()
        self.add()
        self.call("advance", "--reason", "通过")
        self.finish("TASK-001")
        self.call("hold", "--reason", "等待验收确认")
        # 读取不能依赖写锁，也不能写回 JSON 或生成另一份状态。
        (self.directory / ".tasks.lock").touch()
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.directory.iterdir()}
        first = self.show_text()
        self.assertEqual(self.show_text(), first)
        self.assertEqual(self.state(), self.call("show", "--format", "json"))
        after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.directory.iterdir()}
        self.assertEqual(after, before)
        self.assertIn("等待验收确认", first)
        self.assertNotIn("可开始", first)
        self.assertIn("完成判定：尚未满足", first)

    def test_text_view_reports_mixed_states_and_actual_failed_evidence(self):
        self.planning(("AC-001", "AC-002", "AC-003", "AC-004"),
                      ("DES-001", "DES-002", "DES-003", "DES-004"))
        self.add()
        self.add("TASK-002", "AC-002", "DES-002", ("TASK-001",))
        self.add("TASK-003", "AC-003", "DES-003", ("TASK-002",))
        self.add("TASK-004", "AC-003", "DES-003", ("TASK-003",))
        self.add("TASK-005", "AC-004", "DES-004", ("TASK-002",))
        self.add("TASK-006")
        self.call("advance", "--reason", "通过")
        self.finish("TASK-001")
        self.finish("TASK-002")
        self.call("start", "TASK-003")
        self.call("verify", "TASK-003", "--result", "failed", "--check", "刷新后恢复排序",
                  "--observed", "关键词恢复正常\n排序恢复为默认值", "--evidence", "logs/browser.txt")
        self.call("block", "TASK-005", "--reason", "缺少连接配置")
        self.call("skip", "TASK-006", "--reason", "无历史数据")
        output = self.show_text()
        for label, count in (("已完成", 2), ("进行中", 1), ("待处理", 1), ("已阻塞", 1), ("已跳过", 1)):
            self.assertRegex(output, rf"{label}\s+{count}\b")
        self.assertIn("验收覆盖：已完成任务覆盖 2/4", output)
        self.assertIn("设计覆盖：已完成任务覆盖 2/4", output)
        for observation in ("刷新后恢复排序", "关键词恢复正常", "排序恢复为默认值",
                            "logs/browser.txt", "缺少连接配置", "无历史数据"):
            self.assertIn(observation, output)
        positions = [output.index(f"TASK-{index:03d}  ") for index in range(1, 7)]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("可开始 TASK-004", output)
        self.assertIn("TASK-003（进行中）", output)

    def test_text_view_respects_phase_hold_and_skipped_dependency(self):
        self.planning()
        self.add()
        self.add("TASK-002", depends=("TASK-001",))
        self.assertNotIn("可开始", self.show_text())
        self.call("advance", "--reason", "通过")
        self.assertIn("可开始 TASK-001", self.show_text())
        self.assertNotIn("可开始 TASK-002", self.show_text())
        self.call("hold", "--reason", "部署窗口未开放")
        held = self.show_text()
        self.assertNotIn("可开始", held)
        self.assertIn("resume", held.split("下一步\n", 1)[1])
        self.call("resume")
        self.call("skip", "TASK-001", "--reason", "需重新评估")
        skipped = self.show_text()
        self.assertNotIn("可开始 TASK-002", skipped)
        self.assertIn("TASK-001（已跳过）", skipped)

    def test_text_view_does_not_confuse_terminal_tasks_with_coverage(self):
        self.planning(("AC-001", "AC-002"), ("DES-001", "DES-002"))
        self.add()
        self.add("TASK-002", "AC-002", "DES-002")
        self.call("advance", "--reason", "通过")
        self.finish("TASK-001")
        self.call("skip", "TASK-002", "--reason", "暂不执行")
        output = self.show_text()
        self.assertIn("验收覆盖：已完成任务覆盖 1/2", output)
        self.assertIn("设计覆盖：已完成任务覆盖 1/2", output)
        self.assertIn("完成判定：尚未满足", output)
        attention = output.split("需要关注\n", 1)[1].split("下一步\n", 1)[0]
        self.assertIn("AC-002", attention)
        self.assertIn("DES-002", attention)

    def test_text_view_distinguishes_empty_ready_and_completed_workflows(self):
        initial = self.show_text()
        self.assertIn("总计 0 项", initial)
        self.assertIn("验收覆盖：尚未登记", initial)
        self.assertIn("完成判定：尚未满足", initial)
        self.planning()
        self.add()
        self.call("advance", "--reason", "通过")
        self.finish("TASK-001")
        ready = self.show_text()
        self.assertIn("完成判定：状态门槛已满足", ready)
        self.assertIn("advance", ready.split("下一步\n", 1)[1])
        self.call("advance", "--reason", "验收完成")
        completed = self.show_text()
        self.assertIn("阶段：已完成（completed）", completed)
        self.assertIn("完成判定：已完成", completed)
        self.assertNotIn("可开始", completed)

    def test_evidence_dependency_and_phase_gates(self):
        self.rejected("advance", "--acceptance", "AC-001", "--reason", "审查")
        self.planning()
        self.add()
        self.add("TASK-002", depends=("TASK-001",))
        self.rejected("start", "TASK-001")
        self.call("advance", "--reason", "计划覆盖完整")
        self.rejected("start", "TASK-002")
        self.call("start", "TASK-001")
        self.rejected("complete", "TASK-001")
        self.call("verify", "TASK-001", "--result", "failed", "--check", "错误输入",
                  "--observed", "仍返回成功")
        self.rejected("complete", "TASK-001")
        self.call("verify", "TASK-001", "--result", "passed", "--check", "修复后的错误输入",
                  "--observed", "正确返回错误")
        self.call("complete", "TASK-001")
        self.rejected("advance", "--reason", "结束")
        self.finish("TASK-002")
        self.call("advance", "--reason", "所有行为已验证")
        self.assertEqual(self.state()["phase"], "completed")

    def test_reopen_invalidates_transitive_verification(self):
        self.planning()
        self.add()
        self.add("TASK-002", depends=("TASK-001",))
        self.add("TASK-003", depends=("TASK-002",))
        self.add("TASK-004")
        self.call("advance", "--reason", "计划通过")
        for task in ("TASK-001", "TASK-002", "TASK-003", "TASK-004"):
            self.finish(task)
        self.call("advance", "--reason", "通过")
        self.call("reopen", "TASK-001", "--reason", "底层契约变化")
        state = self.state()
        self.assertEqual(state["phase"], "execution")
        for task in state["tasks"][:3]:
            self.assertEqual(task["status"], "pending")
            self.assertEqual(task["verification"]["result"], "not_run")
            self.assertIsNone(task["verification"]["observed"])
        self.assertEqual(state["tasks"][3]["status"], "completed")
        self.rejected("start", "TASK-003")

    def test_skip_cannot_satisfy_dependency_or_acceptance(self):
        self.planning(("AC-001", "AC-002"), ("DES-001", "DES-002"))
        self.add()
        self.rejected("advance", "--reason", "不完整计划")
        self.add("TASK-002", "AC-002", "DES-002")
        self.add("TASK-003", depends=("TASK-002",))
        self.call("advance", "--reason", "计划通过")
        self.finish("TASK-001")
        self.call("skip", "TASK-002", "--reason", "不适用")
        self.rejected("start", "TASK-003")
        self.call("skip", "TASK-003", "--reason", "同样不适用")
        self.rejected("advance", "--reason", "全部已结束")

    def test_dependency_cycles_and_unknown_ids_preserve_file(self):
        self.planning()
        self.add()
        self.add("TASK-002", depends=("TASK-001",))
        self.rejected("update", "TASK-001", "--depends", "TASK-002")
        self.rejected("update", "TASK-001", "--depends", "TASK-999")
        self.rejected("update", "TASK-001", "--acceptance", "AC-999")
        self.rejected("start", "TASK-999")

    def test_blockers_prevent_progress_and_clear_stale_verification(self):
        self.call("hold", "--reason", "需要确认权限边界")
        self.rejected("advance", "--acceptance", "AC-001", "--reason", "跳过问题")
        self.call("resume")
        self.planning()
        self.add()
        self.call("advance", "--reason", "通过")
        self.call("start", "TASK-001")
        self.call("verify", "TASK-001", "--result", "passed", "--check", "旧环境",
                  "--observed", "正确")
        self.call("block", "TASK-001", "--reason", "测试环境变更，需恢复后复测")
        self.rejected("start", "TASK-001")
        self.call("unblock", "TASK-001")
        self.call("start", "TASK-001")
        self.rejected("complete", "TASK-001")

    def test_modes_and_replanning_invalidate_old_completion(self):
        self.planning()
        self.add()
        self.call("advance", "--reason", "通过")
        self.finish("TASK-001")
        self.call("advance", "--reason", "通过")
        self.call("mode", "--mode", "standard", "--reason", "发现新增安全边界")
        self.rejected("mode", "--mode", "lightweight", "--reason", "缩短文档")
        self.call("replan", "--acceptance", "AC-001", "AC-002", "--reason", "重新审查需求和设计")
        state = self.state()
        self.assertEqual(state["phase"], "planning")
        self.assertEqual(state["tasks"][0]["status"], "pending")
        self.assertEqual(state["tasks"][0]["verification"]["result"], "not_run")
        self.rejected("advance", "--reason", "缺少新任务")
        self.add("TASK-002", "AC-002")
        self.call("advance", "--reason", "新范围已覆盖")

    def test_stale_revision_lock_and_reinitialization_preserve_file(self):
        old_revision = self.state()["revision"]
        self.call("hold", "--reason", "需求问题")
        self.rejected("resume", "--expect-revision", str(old_revision))
        self.rejected("init", "--mode", "standard", "--reason", "替换旧任务")
        lock = self.directory / ".tasks.lock"
        lock.touch()
        self.rejected("resume")
        self.assertTrue(lock.exists())
        lock.unlink()
        self.call("resume", "--expect-revision", str(old_revision + 1))
        self.assertFalse(lock.exists())

    def test_invalid_json_and_unknown_schema_are_not_replaced(self):
        valid = self.state()
        self.path.write_text('{"schema_version":', encoding="utf-8")
        self.rejected("validate")
        self.rejected("hold", "--reason", "不要重置损坏文件")
        self.assertFalse((self.directory / ".tasks.lock").exists())
        for damaged in ({**valid, "schema_version": 2}, {**valid, "unknown": True}):
            with self.subTest(damaged=damaged):
                self.path.write_text(json.dumps(damaged), encoding="utf-8")
                self.rejected("validate")
                self.rejected("hold", "--reason", "不要重置未知格式")

    def test_symlink_state_does_not_overwrite_target(self):
        target = self.directory / "original.json"
        self.path.rename(target)
        self.path.symlink_to(target)
        self.rejected("hold", "--reason", "越界修改")
        self.assertTrue(self.path.is_symlink())


if __name__ == "__main__":
    unittest.main()

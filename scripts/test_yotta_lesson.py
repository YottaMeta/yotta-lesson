#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""元案 yotta-lesson 内核契约测试（TDD：先红后绿）。"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import yotta_lesson as yl  # noqa: E402

NOW = "2026-09-24T00:00:00Z"
STANDARD = "示例课程标准（2022 年版）· 示例条目"


def sample_map():
    return {
        "schema_version": yl.SCHEMA_VERSION,
        "subject": "数学",
        "grade": "七年级上",
        "lessons": [
            {
                "id": "L1",
                "title": "认识一元一次方程",
                "unit": "一元一次方程",
                "periods": 1,
                "knowledge": ["一元一次方程的定义", "方程的解"],
                "key_points": ["一元一次方程的定义"],
                "difficulties": ["由实际问题抽象出方程"],
                "misconceptions": ["把含未知数的式子都当方程"],
                "standard": STANDARD,
            }
        ],
    }


OK_PLAN_TEXT = (
    "课题：认识一元一次方程\n"
    "来源：示例课程标准（2022 年版）\n"
    "1. 导入 5 分钟\n"
    "2. 探究一元一次方程的定义 14 分钟\n"
    "3. 例题精讲 11 分钟\n"
    "4. 练习巩固 11 分钟\n"
    "5. 小结与作业 4 分钟\n"
    "合计 45 分钟\n"
    "学习中要掌握一元一次方程的定义，并理解方程的解。\n"
)


class MapTest(unittest.TestCase):
    def test_map_loads_with_index(self):
        lesson_map = yl.load_map(sample_map(), "map")
        self.assertEqual(lesson_map["by_id"]["L1"]["periods"], 1)
        self.assertEqual(lesson_map["subject"], "数学")

    def test_schema_version_mismatch_rejected(self):
        payload = sample_map()
        payload["schema_version"] = "9.9"
        with self.assertRaises(yl.ConfigError):
            yl.load_map(payload, "map")

    def test_duplicate_lesson_id_rejected(self):
        payload = sample_map()
        payload["lessons"].append(dict(payload["lessons"][0]))
        with self.assertRaises(yl.ConfigError):
            yl.load_map(payload, "map")

    def test_missing_standard_rejected(self):
        payload = sample_map()
        del payload["lessons"][0]["standard"]
        with self.assertRaises(yl.ConfigError) as ctx:
            yl.load_map(payload, "map")
        self.assertIn("standard", str(ctx.exception))

    def test_empty_knowledge_rejected(self):
        payload = sample_map()
        payload["lessons"][0]["knowledge"] = []
        with self.assertRaises(yl.ConfigError):
            yl.load_map(payload, "map")

    def test_bad_periods_rejected(self):
        payload = sample_map()
        payload["lessons"][0]["periods"] = 0
        with self.assertRaises(yl.ConfigError):
            yl.load_map(payload, "map")

    def test_missing_file_is_config_error(self):
        with self.assertRaises(yl.ConfigError):
            yl.load_map("no-such-map.json", "map")


class StructureTest(unittest.TestCase):
    def test_defaults_used_when_missing(self):
        structure = yl.load_structure(None)
        self.assertEqual(structure["minutes_per_period"], 45)
        self.assertEqual(len(structure["stages"]), 5)

    def test_partial_override(self):
        structure = yl.load_structure({"minutes_per_period": 40})
        self.assertEqual(structure["minutes_per_period"], 40)
        self.assertEqual(len(structure["stages"]), 5)

    def test_duplicate_stage_rejected(self):
        with self.assertRaises(yl.ConfigError):
            yl.load_structure({"stages": [
                {"id": "a", "name": "A", "ratio": 1},
                {"id": "a", "name": "B", "ratio": 1},
            ]})

    def test_non_positive_ratio_rejected(self):
        with self.assertRaises(yl.ConfigError):
            yl.load_structure({"stages": [{"id": "a", "name": "A", "ratio": 0}]})

    def test_unknown_required_stage_rejected(self):
        with self.assertRaises(yl.ConfigError):
            yl.load_structure({"required_stages": ["nope"]})

    def test_keywords_override(self):
        structure = yl.load_structure({"check_keywords": {"summary": ["收束"]}})
        self.assertEqual(structure["check_keywords"]["summary"], ["收束"])


class AllocateTest(unittest.TestCase):
    def test_minutes_sum_exactly(self):
        structure = yl.load_structure(None)
        for total in (45, 90, 40, 135):
            minutes = yl.allocate_minutes(total, structure["stages"])
            self.assertEqual(sum(minutes), total)
            self.assertTrue(all(value >= 1 for value in minutes))

    def test_allocation_is_deterministic(self):
        stages = [{"id": "a", "name": "A", "ratio": 1},
                  {"id": "b", "name": "B", "ratio": 1},
                  {"id": "c", "name": "C", "ratio": 1}]
        self.assertEqual(yl.allocate_minutes(10, stages), yl.allocate_minutes(10, stages))

    def test_too_few_minutes_rejected(self):
        stages = [{"id": str(i), "name": "S", "ratio": 1} for i in range(5)]
        with self.assertRaises(yl.ConfigError):
            yl.allocate_minutes(3, stages)


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.lesson = yl.load_map(sample_map(), "map")["by_id"]["L1"]
        self.structure = yl.load_structure(None)

    def test_objectives_cover_knowledge_with_sources(self):
        plan = yl.build_plan(self.lesson, self.structure, now=NOW)
        self.assertEqual([o["knowledge"] for o in plan["objectives"]],
                         ["一元一次方程的定义", "方程的解"])
        self.assertTrue(all(o["source"] == STANDARD for o in plan["objectives"]))

    def test_stage_minutes_sum_to_total(self):
        plan = yl.build_plan(self.lesson, self.structure, now=NOW)
        self.assertEqual(sum(s["minutes"] for s in plan["stages"]), 45)
        self.assertEqual(plan["lesson"]["total_minutes"], 45)

    def test_periods_override_is_recorded(self):
        plan = yl.build_plan(self.lesson, self.structure, periods=2, now=NOW)
        self.assertEqual(plan["lesson"]["total_minutes"], 90)
        self.assertTrue(any(f["kind"] == "periods_override" for f in plan["findings"]))

    def test_missing_misconceptions_is_flagged(self):
        lesson = dict(self.lesson)
        lesson["misconceptions"] = []
        plan = yl.build_plan(lesson, self.structure, now=NOW)
        self.assertTrue(any(f["kind"] == "no_misconceptions" for f in plan["findings"]))

    def test_plan_is_deterministic_except_timestamp(self):
        first = yl.build_plan(self.lesson, self.structure, now=NOW)
        second = yl.build_plan(self.lesson, self.structure, now=NOW)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_markdown_has_sections(self):
        text = yl.render_plan_markdown(yl.build_plan(self.lesson, self.structure, now=NOW))
        for marker in ("教案骨架", "学习目标", "教学环节与时间分配", "备课提示", "免责"):
            self.assertIn(marker, text)

    def test_json_contract_keys(self):
        plan = yl.build_plan(self.lesson, self.structure, now=NOW)
        for key in ("schema_version", "tool", "tool_version", "generated_at", "lesson",
                    "objectives", "key_points", "difficulties", "misconceptions", "stages",
                    "checklist", "findings", "sources", "disclaimer"):
            self.assertIn(key, plan)


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.lesson = yl.load_map(sample_map(), "map")["by_id"]["L1"]
        self.structure = yl.load_structure(None)

    def test_complete_plan_has_no_findings(self):
        result = yl.check_plan(OK_PLAN_TEXT, self.lesson, self.structure)
        self.assertEqual(result["findings"], [])

    def test_missing_knowledge_detected(self):
        text = OK_PLAN_TEXT.replace("方程的解", "解的定义")
        result = yl.check_plan(text, self.lesson, self.structure)
        self.assertTrue(any(f["kind"] == "knowledge_missing" for f in result["findings"]))

    def test_missing_stage_detected(self):
        text = "\n".join(line for line in OK_PLAN_TEXT.splitlines()
                         if "练习" not in line and "巩固" not in line and "变式" not in line)
        result = yl.check_plan(text, self.lesson, self.structure)
        self.assertTrue(any(f["kind"] == "stage_missing" for f in result["findings"]))

    def test_missing_source_detected(self):
        text = OK_PLAN_TEXT.replace("示例课程标准（2022 年版）", "课程标准")
        result = yl.check_plan(text, self.lesson, self.structure)
        self.assertTrue(any(f["kind"] == "source_missing" for f in result["findings"]))

    def test_missing_time_detected(self):
        text = "\n".join(line for line in OK_PLAN_TEXT.splitlines() if "分钟" not in line)
        result = yl.check_plan(text, self.lesson, self.structure)
        self.assertTrue(any(f["kind"] == "time_missing" for f in result["findings"]))

    def test_minutes_mismatch_detected(self):
        text = OK_PLAN_TEXT.replace("合计 45 分钟", "合计 40 分钟")
        result = yl.check_plan(text, self.lesson, self.structure)
        self.assertTrue(any(f["kind"] == "minutes_mismatch" for f in result["findings"]))

    def test_findings_are_sorted(self):
        text = "空教案"
        result = yl.check_plan(text, self.lesson, self.structure)
        keys = [(f["kind"], f["detail"]) for f in result["findings"]]
        self.assertEqual(keys, sorted(keys))
        self.assertGreaterEqual(len(result["findings"]), 4)

    def test_markdown_lists_findings(self):
        text = yl.render_check_markdown(yl.check_plan("空教案", self.lesson, self.structure))
        self.assertIn("缺口清单", text)
        self.assertIn("knowledge_missing", text)


class SecurityTest(unittest.TestCase):
    def test_engine_has_no_network_imports(self):
        source = (SCRIPTS_DIR / "yotta_lesson.py").read_text(encoding="utf-8")
        for marker in ("import urllib", "import socket", "import requests", "http.client"):
            self.assertNotIn(marker, source)

    def test_engine_has_no_author_machine_paths(self):
        source = (SCRIPTS_DIR / "yotta_lesson.py").read_text(encoding="utf-8")
        self.assertNotIn("D:\\AI_WorkDir", source)
        self.assertNotIn("C:\\Users", source)

    def test_output_directory_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(yl.InputError):
                yl.resolve_output_path(td)

    def test_output_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(yl.InputError):
                yl.resolve_output_path(os.path.join(td, "..", "x.md"))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.map = self.dir / "map.json"
        self.map.write_text(json.dumps(sample_map(), ensure_ascii=False), encoding="utf-8")
        self.plan = self.dir / "plan.md"
        self.plan.write_text(OK_PLAN_TEXT, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cli_version(self):
        self.assertEqual(yl.main(["--version"]), 0)

    def test_cli_plan_markdown_to_file(self):
        out = self.dir / "out.md"
        code = yl.main(["plan", "--map", str(self.map), "--lesson", "L1", "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertIn("教案骨架", out.read_text(encoding="utf-8"))

    def test_cli_plan_json(self):
        out = self.dir / "out.json"
        yl.main(["plan", "--map", str(self.map), "--lesson", "L1",
                 "--format", "json", "--out", str(out)])
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["tool"], "yotta-lesson")

    def test_cli_check_clean_and_gate(self):
        self.assertEqual(yl.main(["check", "--plan", str(self.plan), "--map", str(self.map),
                                  "--lesson", "L1", "--gate", "findings=1"]), 0)

    def test_cli_check_gap_triggers_gate(self):
        gap = self.dir / "gap.md"
        gap.write_text("空教案\n", encoding="utf-8")
        code = yl.main(["check", "--plan", str(gap), "--map", str(self.map),
                        "--lesson", "L1", "--gate", "findings=1"])
        self.assertEqual(code, 1)

    def test_cli_check_stdin(self):
        out = self.dir / "stdin.json"
        code = yl.main(["check", "--stdin", "--map", str(self.map), "--lesson", "L1",
                        "--format", "json", "--out", str(out)], stdin_text=OK_PLAN_TEXT)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["summary"]["findings"], 0)

    def test_cli_map_validate_and_list(self):
        self.assertEqual(yl.main(["map", "validate", "--map", str(self.map)]), 0)
        self.assertEqual(yl.main(["map", "list", "--map", str(self.map)]), 0)
        self.assertEqual(yl.main(["map", "show", "--map", str(self.map), "--lesson", "L1"]), 0)

    def test_cli_unknown_lesson_exit_three(self):
        self.assertEqual(yl.main(["plan", "--map", str(self.map), "--lesson", "L9"]), 3)

    def test_cli_missing_map_exit_three(self):
        self.assertEqual(yl.main(["plan", "--map", str(self.dir / "nope.json"),
                                  "--lesson", "L1"]), 3)

    def test_cli_missing_plan_file_exit_two(self):
        self.assertEqual(yl.main(["check", "--plan", str(self.dir / "nope.md"),
                                  "--map", str(self.map), "--lesson", "L1"]), 2)

    def test_cli_unknown_command_exit_two(self):
        self.assertEqual(yl.main(["nope"]), 2)

    def test_cli_template_writes_files(self):
        out_dir = self.dir / "tpl"
        self.assertEqual(yl.main(["template", "--output-dir", str(out_dir)]), 0)
        names = sorted(p.name for p in out_dir.iterdir())
        self.assertEqual(names, ["lesson-map.json", "structure.json"])
        yl.load_map(json.loads((out_dir / "lesson-map.json").read_text(encoding="utf-8")), "tpl")
        yl.load_structure(json.loads((out_dir / "structure.json").read_text(encoding="utf-8")))


class DocContractTest(unittest.TestCase):
    root = SCRIPTS_DIR.parent

    def _read(self, *parts):
        return self.root.joinpath(*parts).read_text(encoding="utf-8")

    def test_skill_frontmatter_matches_engine(self):
        front = self._read("SKILL.md").split("---", 2)[1]
        self.assertIn("name: yotta-lesson", front)
        self.assertIn("version: %s" % yl.VERSION, front)
        self.assertIn("license: MIT", front)
        self.assertIn("触发", front)
        self.assertIn("边界", front)

    def test_references_are_complete(self):
        for name in ("map-format.md", "plan-format.md", "copyright.md"):
            text = self._read("references", name)
            self.assertGreater(len(text), 700, name)

    def test_readme_four_ways(self):
        readme = self._read("README.md")
        self.assertIn("npx -y @yottameta/yotta-lesson", readme)
        self.assertIn("git clone https://github.com/YottaMeta/yotta-lesson", readme)
        self.assertIn("Download ZIP", readme)
        self.assertIn("install.sh --agent", readme)
        self.assertNotIn("npx skills", readme)

    def test_chinese_readme_four_ways(self):
        readme = self._read("README.zh-CN.md")
        self.assertIn("方式一", readme)
        self.assertIn("方式四", readme)
        self.assertIn("install.sh --agent", readme)

    def test_disclaimer_documented(self):
        for name in ("SKILL.md", "README.zh-CN.md", "references/copyright.md"):
            self.assertIn("备课辅助", self._read(*name.split("/")), name)

    def test_plan_format_doc_covers_json_keys(self):
        lesson = yl.load_map(sample_map(), "map")["by_id"]["L1"]
        plan = yl.build_plan(lesson, yl.load_structure(None), now=NOW)
        doc = self._read("references", "plan-format.md")
        for key in plan:
            self.assertIn("`%s`" % key, doc, key)

    def test_finding_kinds_documented(self):
        doc = self._read("references", "plan-format.md")
        for kind in ("knowledge_missing", "stage_missing", "source_missing",
                     "time_missing", "minutes_mismatch"):
            self.assertIn(kind, doc)


class FixtureTest(unittest.TestCase):
    fixtures = SCRIPTS_DIR / "fixtures" / "samples"

    def test_fixture_map_and_plans(self):
        lesson_map = yl.load_map(self.fixtures / "lesson-map.json", "fixture")
        structure = yl.load_structure(None)
        clean = (self.fixtures / "plan-complete.md").read_text(encoding="utf-8")
        gap = (self.fixtures / "plan-gap.md").read_text(encoding="utf-8")
        lesson = lesson_map["by_id"]["L1"]
        self.assertEqual(yl.check_plan(clean, lesson, structure)["findings"], [])
        self.assertGreaterEqual(len(yl.check_plan(gap, lesson, structure)["findings"]), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

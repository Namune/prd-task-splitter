#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRD 智能任务拆解器 - 边界测试 & 压力测试
覆盖：空输入、超长输入、特殊字符、纯英文、格式混乱、重复内容等极端场景
"""

import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import PRDAnalyzer, ReportFormatter, TaskType


# ─── 各种极端 PRD 样本 ────────────────────────────────────────────

EMPTY_PRD = ""

WHITESPACE_ONLY = "   \n\n\t\n   "

SINGLE_LINE = "用户登录功能"

VERY_LONG_PRD = """
# 超大型电商平台需求文档

## 用户模块
""" + "\n".join([f"- 支持功能{i}，用户可以进行操作{i}，系统需要处理请求{i}" for i in range(1, 200)])

SPECIAL_CHARS_PRD = """
# 特殊字符测试 <>&"'

## 模块①②③
支持用户登录/注册（手机号+密码）。
系统需要处理 SQL: SELECT * FROM users。
API接口：/api/v1/user?id=1&type=2。
包含emoji：🎉🚀💡的功能描述。
"""

ENGLISH_PRD = """
# User Management System

## Authentication
Support user login with username and password.
Implement JWT token authentication.
The system should validate token expiry.

## Profile
Users can update their profile information.
Support avatar upload with image processing.
"""

MIXED_FORMAT_PRD = """
# 混合格式需求

一、用户管理
1. 支持用户注册
2. 支持用户登录
【权限控制】
- 管理员可以管理用户
* 普通用户只能查看

二、数据管理
数据库需要建立索引。
系统需要定时备份数据。
"""

DUPLICATE_CONTENT_PRD = """
# 重复内容测试

## 登录模块
支持用户登录。
支持用户登录。
支持用户登录。
用户可以输入账号密码登录。
用户可以输入账号密码登录。
"""

NO_MODULES_PRD = """
这是一个没有明确模块划分的需求文档。
系统需要支持用户注册和登录功能。
用户可以修改个人信息。
支持上传头像图片。
展示用户订单列表页面。
订单详情接口需要返回数据。
"""

RISK_HEAVY_PRD = """
# 高风险需求文档

## 支付模块
支持支付宝和微信支付，调用第三方支付接口。
涉及金额计算，需要处理高并发场景，QPS要求1000。
历史订单数据迁移，存量数据约1000万条。
需要实现实时对账功能，对接银行系统。
涉及用户隐私数据，需要加密存储。
"""

PERFORMANCE_PRD = """
# 性能需求文档

## 核心接口
接口响应时间要求500毫秒以内。
系统需要支持1000并发用户。
数据库查询QPS要求达到5000。
"""

VAGUE_HEAVY_PRD = """
# 模糊需求文档

## 功能模块
系统需要尽快完成，界面要友好，性能要稳定。
支持适当的权限管理，实现灵活的配置。
用户体验要好，操作要简单方便。
系统要智能，能自动处理各种情况。
功能要完善，等后续再优化。
"""

ACCEPTANCE_CRITERIA_PRD = """
# 含验收标准的需求

## 登录功能
支持手机号登录。

验收标准：
- 输入正确手机号和验证码，登录成功
- 输入错误验证码，提示错误信息
- 验证码5分钟内有效
"""


class TestEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def setUp(self):
        self.analyzer = PRDAnalyzer()
        self.formatter = ReportFormatter()

    def test_empty_string_does_not_crash(self):
        """空字符串不崩溃"""
        report = self.analyzer.analyze(EMPTY_PRD)
        self.assertIsNotNone(report)
        self.assertIsInstance(report.tasks, list)

    def test_whitespace_only_does_not_crash(self):
        """纯空白不崩溃"""
        report = self.analyzer.analyze(WHITESPACE_ONLY)
        self.assertIsNotNone(report)

    def test_single_line_does_not_crash(self):
        """单行内容不崩溃"""
        report = self.analyzer.analyze(SINGLE_LINE)
        self.assertIsNotNone(report)
        self.assertIsInstance(report.tasks, list)

    def test_very_long_prd_performance(self):
        """超长 PRD（200个功能点）在合理时间内完成"""
        import time
        start = time.time()
        report = self.analyzer.analyze(VERY_LONG_PRD)
        elapsed = time.time() - start
        self.assertLess(elapsed, 10.0, f'超长 PRD 分析耗时 {elapsed:.2f}s，超过10秒')
        self.assertIsNotNone(report)

    def test_very_long_prd_task_count_reasonable(self):
        """超长 PRD 任务数量有上限保护（不超过300）"""
        report = self.analyzer.analyze(VERY_LONG_PRD)
        self.assertLessEqual(len(report.tasks), 300)

    def test_special_characters_do_not_crash(self):
        """特殊字符（HTML、SQL、emoji）不崩溃"""
        report = self.analyzer.analyze(SPECIAL_CHARS_PRD)
        self.assertIsNotNone(report)
        self.assertIsInstance(report.tasks, list)

    def test_english_prd_works(self):
        """纯英文 PRD 不崩溃，能提取任务"""
        report = self.analyzer.analyze(ENGLISH_PRD)
        self.assertIsNotNone(report)
        self.assertIsInstance(report.tasks, list)

    def test_mixed_format_prd(self):
        """混合格式（中文序号+Markdown+【】）正常解析"""
        report = self.analyzer.analyze(MIXED_FORMAT_PRD)
        self.assertGreater(len(report.tasks), 0)

    def test_duplicate_content_deduplication(self):
        """重复内容不产生重复任务"""
        report = self.analyzer.analyze(DUPLICATE_CONTENT_PRD)
        titles = [t.title for t in report.tasks]
        # 重复的功能描述不应该产生完全相同的任务标题
        self.assertEqual(len(titles), len(set(titles)), '存在重复任务标题')

    def test_no_modules_fallback(self):
        """无模块划分时兜底提取正常工作"""
        report = self.analyzer.analyze(NO_MODULES_PRD)
        self.assertGreater(len(report.tasks), 0)

    def test_task_ids_always_unique(self):
        """任意 PRD 的任务 ID 都唯一"""
        for prd in [SAMPLE_PRD_1, SAMPLE_PRD_2, MIXED_FORMAT_PRD, RISK_HEAVY_PRD]:
            self.analyzer = PRDAnalyzer()
            report = self.analyzer.analyze(prd)
            ids = [t.id for t in report.tasks]
            self.assertEqual(len(ids), len(set(ids)), f'发现重复任务ID: {ids}')

    def test_estimate_hours_always_positive(self):
        """所有任务工时估算必须大于0"""
        report = self.analyzer.analyze(MIXED_FORMAT_PRD)
        for task in report.tasks:
            self.assertGreater(task.estimate_hours, 0,
                               f'任务 {task.id} 工时为0或负数')

    def test_summary_hours_equals_sum(self):
        """summary 中的总工时等于所有任务工时之和"""
        report = self.analyzer.analyze(RISK_HEAVY_PRD)
        expected = sum(t.estimate_hours for t in report.tasks)
        self.assertEqual(report.summary['total_hours'], expected)

    def test_summary_task_count_matches(self):
        """summary 中的任务数等于实际任务列表长度"""
        report = self.analyzer.analyze(MIXED_FORMAT_PRD)
        self.assertEqual(report.summary['total_tasks'], len(report.tasks))

    def test_acceptance_criteria_never_empty(self):
        """每个任务都有至少一条验收标准"""
        report = self.analyzer.analyze(MIXED_FORMAT_PRD)
        for task in report.tasks:
            self.assertGreater(len(task.acceptance_criteria), 0,
                               f'任务 {task.id} 没有验收标准')

    def test_risk_detection_in_risk_heavy_prd(self):
        """高风险 PRD 能检测出多个风险"""
        report = self.analyzer.analyze(RISK_HEAVY_PRD)
        all_risks = [r for t in report.tasks for r in t.risks]
        self.assertGreaterEqual(len(all_risks), 3,
                                f'高风险PRD只检测到 {len(all_risks)} 个风险')

    def test_vague_word_detection_count(self):
        """模糊词汇密集的 PRD 能检测出多个警告"""
        report = self.analyzer.analyze(VAGUE_HEAVY_PRD)
        vague_issues = [i for i in report.issues if '模糊词汇' in i.issue]
        self.assertGreaterEqual(len(vague_issues), 3,
                                f'只检测到 {len(vague_issues)} 个模糊词汇')

    def test_acceptance_criteria_prd_no_critical_issue(self):
        """含验收标准的 PRD 不应报告缺少验收标准"""
        report = self.analyzer.analyze(ACCEPTANCE_CRITERIA_PRD)
        critical_ac = [i for i in report.issues
                       if i.severity == 'critical' and '验收标准' in i.issue]
        self.assertEqual(len(critical_ac), 0,
                         '含验收标准的PRD不应报告缺少验收标准')

    def test_performance_prd_no_perf_issue(self):
        """含性能指标的 PRD 不应报告缺少性能指标"""
        report = self.analyzer.analyze(PERFORMANCE_PRD)
        perf_issues = [i for i in report.issues if '性能指标' in i.issue]
        self.assertEqual(len(perf_issues), 0,
                         '含性能指标的PRD不应报告缺少性能指标')

    def test_dependency_ids_exist(self):
        """依赖的任务 ID 必须在任务列表中存在"""
        report = self.analyzer.analyze(MIXED_FORMAT_PRD)
        all_ids = {t.id for t in report.tasks}
        for task in report.tasks:
            for dep_id in task.depends_on:
                self.assertIn(dep_id, all_ids,
                              f'任务 {task.id} 依赖了不存在的任务 {dep_id}')

    def test_task_type_always_valid(self):
        """所有任务类型必须是合法值"""
        valid_types = {t.value for t in TaskType}
        report = self.analyzer.analyze(MIXED_FORMAT_PRD)
        for task in report.tasks:
            self.assertIn(task.task_type, valid_types,
                          f'任务 {task.id} 类型 {task.task_type} 不合法')

    def test_priority_always_valid(self):
        """所有任务优先级必须是合法值"""
        from main import Priority
        valid_priorities = {p.value for p in Priority}
        report = self.analyzer.analyze(MIXED_FORMAT_PRD)
        for task in report.tasks:
            self.assertIn(task.priority, valid_priorities,
                          f'任务 {task.id} 优先级 {task.priority} 不合法')


class TestOutputFormats(unittest.TestCase):
    """输出格式严格测试"""

    def setUp(self):
        self.analyzer = PRDAnalyzer()
        self.formatter = ReportFormatter()
        self.report = self.analyzer.analyze(MIXED_FORMAT_PRD)

    def test_markdown_no_unclosed_code_blocks(self):
        """Markdown 中代码块必须成对出现"""
        md = self.formatter.to_markdown(self.report)
        count = md.count('```')
        self.assertEqual(count % 2, 0, f'代码块未闭合，共 {count} 个反引号组')

    def test_markdown_all_task_ids_present(self):
        """Markdown 报告包含所有任务 ID"""
        md = self.formatter.to_markdown(self.report)
        for task in self.report.tasks:
            self.assertIn(task.id, md, f'Markdown 中缺少任务 {task.id}')

    def test_csv_correct_column_count(self):
        """CSV 每行列数一致"""
        csv_str = self.formatter.to_csv(self.report)
        lines = [l for l in csv_str.strip().split('\n') if l]
        import csv, io
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        col_count = len(rows[0])
        for i, row in enumerate(rows[1:], 2):
            self.assertEqual(len(row), col_count,
                             f'CSV 第 {i} 行列数 {len(row)} 与表头 {col_count} 不一致')

    def test_csv_no_empty_task_id(self):
        """CSV 中任务 ID 列不为空"""
        import csv, io
        csv_str = self.formatter.to_csv(self.report)
        reader = csv.DictReader(io.StringIO(csv_str))
        for row in reader:
            self.assertTrue(row['任务ID'].strip(),
                            f'CSV 中存在空任务ID，行内容：{row}')

    def test_json_schema_valid(self):
        """JSON 输出包含所有必要字段"""
        json_str = self.formatter.to_json(self.report)
        data = json.loads(json_str)
        required_keys = ['prd_title', 'analyzed_at', 'summary', 'modules', 'tasks', 'issues']
        for key in required_keys:
            self.assertIn(key, data, f'JSON 缺少字段: {key}')

    def test_json_task_schema(self):
        """JSON 中每个任务包含必要字段"""
        json_str = self.formatter.to_json(self.report)
        data = json.loads(json_str)
        required_task_keys = ['id', 'module', 'title', 'task_type',
                              'priority', 'estimate_hours', 'depends_on',
                              'acceptance_criteria', 'risks']
        for task in data['tasks']:
            for key in required_task_keys:
                self.assertIn(key, task, f'任务 JSON 缺少字段: {key}')

    def test_json_summary_schema(self):
        """JSON summary 包含必要统计字段"""
        json_str = self.formatter.to_json(self.report)
        data = json.loads(json_str)
        required = ['total_tasks', 'total_hours', 'estimated_working_days',
                    'by_type', 'by_priority', 'by_module']
        for key in required:
            self.assertIn(key, data['summary'], f'summary 缺少字段: {key}')

    def test_all_formats_handle_empty_tasks(self):
        """空任务列表时三种格式都不崩溃"""
        from main import AnalysisReport
        empty_report = AnalysisReport(
            prd_title='空报告',
            analyzed_at='2026-01-01',
            modules=[],
            tasks=[],
            issues=[],
            summary={
                'total_tasks': 0, 'total_hours': 0,
                'estimated_working_days': 0,
                'by_type': {}, 'by_priority': {}, 'by_module': {},
                'total_issues': 0, 'issue_severity': {}
            }
        )
        try:
            self.formatter.to_markdown(empty_report)
            self.formatter.to_csv(empty_report)
            self.formatter.to_json(empty_report)
        except Exception as e:
            self.fail(f'空任务列表时格式化崩溃: {e}')

    def test_special_chars_in_csv_escaped(self):
        """含特殊字符的 PRD 生成的 CSV 可以被正确解析"""
        import csv, io
        report = self.analyzer.analyze(SPECIAL_CHARS_PRD)
        csv_str = self.formatter.to_csv(report)
        try:
            reader = csv.reader(io.StringIO(csv_str))
            rows = list(reader)
            self.assertGreater(len(rows), 0)
        except Exception as e:
            self.fail(f'含特殊字符的 CSV 解析失败: {e}')

    def test_json_chinese_encoding(self):
        """JSON 输出中文字符正确编码"""
        report = self.analyzer.analyze(MIXED_FORMAT_PRD)
        json_str = self.formatter.to_json(report)
        data = json.loads(json_str)
        # 确保中文没有被转义成 \uXXXX
        self.assertNotIn(r'\u7528\u6237', json_str,  # "用户" 的转义
                         'JSON 中文字符被错误转义')


# ─── 辅助 PRD 样本 ────────────────────────────────────────────────

SAMPLE_PRD_1 = """
# 项目A需求
## 登录
支持手机号登录。
展示登录页面。
"""

SAMPLE_PRD_2 = """
# 项目B需求
## 注册
支持邮箱注册。
数据库需要建立用户表。
"""


def run_all_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestOutputFormats))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print('\n' + '=' * 60)
    print(f'边界测试总数: {result.testsRun}')
    print(f'成功: {result.testsRun - len(result.failures) - len(result.errors)}')
    print(f'失败: {len(result.failures)}')
    print(f'错误: {len(result.errors)}')
    print('=' * 60)
    return result.wasSuccessful()


if __name__ == '__main__':
    sys.exit(0 if run_all_tests() else 1)

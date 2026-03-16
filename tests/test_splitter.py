#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PRD 智能任务拆解器 - 单元测试"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import PRDAnalyzer, ReportFormatter, TaskType, PRDIssue


SAMPLE_PRD = """
# 用户登录功能需求

## 手机号登录
支持手机号+验证码登录。
用户可以输入手机号获取短信验证码。
系统需要校验验证码有效期为5分钟。

## 个人信息
用户可以修改昵称和头像。
支持上传头像图片，调用第三方图片存储接口。
展示用户基本信息页面。

## 订单查询
展示订单列表页面，支持筛选。
订单详情接口需要返回完整数据。
数据库需要建立订单索引。
"""

VAGUE_PRD = """
# 模糊需求文档
系统需要尽快完成，界面要友好，性能要稳定。
支持适当的权限管理，实现灵活的配置。
"""

MINIMAL_PRD = """
# 最小需求
- 用户登录页面
- 后端登录接口
"""


class TestPRDAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = PRDAnalyzer()

    def test_extract_title(self):
        """测试标题提取"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        self.assertIn('用户登录', report.prd_title)

    def test_extract_modules(self):
        """测试模块识别"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        self.assertGreater(len(report.modules), 0)
        module_names = ' '.join(report.modules)
        self.assertTrue(
            '登录' in module_names or '个人' in module_names or '订单' in module_names
        )

    def test_task_extraction(self):
        """测试任务提取"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        self.assertGreater(len(report.tasks), 0)

    def test_task_has_required_fields(self):
        """测试任务字段完整性"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        for task in report.tasks:
            self.assertTrue(task.id.startswith('T'))
            self.assertIn(task.task_type, [t.value for t in TaskType])
            self.assertGreater(task.estimate_hours, 0)
            self.assertIsInstance(task.acceptance_criteria, list)
            self.assertGreater(len(task.acceptance_criteria), 0)

    def test_task_type_classification_frontend(self):
        """测试前端任务识别"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        types = [t.task_type for t in report.tasks]
        self.assertIn(TaskType.FRONTEND.value, types)

    def test_task_type_classification_backend(self):
        """测试后端任务识别"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        types = [t.task_type for t in report.tasks]
        self.assertIn(TaskType.BACKEND.value, types)

    def test_task_type_classification_database(self):
        """测试数据库任务识别"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        types = [t.task_type for t in report.tasks]
        self.assertIn(TaskType.DATABASE.value, types)

    def test_dependency_inference(self):
        """测试依赖关系推断"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        # 前端任务应该依赖后端任务
        frontend_tasks = [t for t in report.tasks if t.task_type == TaskType.FRONTEND.value]
        backend_ids = {t.id for t in report.tasks if t.task_type == TaskType.BACKEND.value}
        for ft in frontend_tasks:
            for dep in ft.depends_on:
                self.assertIn(dep, backend_ids)

    def test_vague_word_detection(self):
        """测试模糊词汇检测"""
        report = self.analyzer.analyze(VAGUE_PRD)
        vague_issues = [i for i in report.issues if '模糊词汇' in i.issue]
        self.assertGreater(len(vague_issues), 0)

    def test_missing_acceptance_criteria_detection(self):
        """测试缺少验收标准检测"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        ac_issues = [i for i in report.issues if '验收标准' in i.issue]
        self.assertGreater(len(ac_issues), 0)

    def test_missing_error_flow_detection(self):
        """测试缺少异常流程检测"""
        report = self.analyzer.analyze(MINIMAL_PRD)
        error_issues = [i for i in report.issues if '异常' in i.issue]
        self.assertGreater(len(error_issues), 0)

    def test_third_party_risk_detection(self):
        """测试第三方依赖风险检测"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        risk_tasks = [t for t in report.tasks if t.risks]
        self.assertGreater(len(risk_tasks), 0)

    def test_summary_total_hours(self):
        """测试工时汇总计算"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        expected = sum(t.estimate_hours for t in report.tasks)
        self.assertEqual(report.summary['total_hours'], expected)

    def test_summary_by_type(self):
        """测试按类型统计"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        self.assertIn('by_type', report.summary)
        total_from_type = sum(report.summary['by_type'].values())
        self.assertEqual(total_from_type, report.summary['total_tasks'])

    def test_summary_working_days(self):
        """测试工作日估算"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        self.assertGreater(report.summary['estimated_working_days'], 0)

    def test_minimal_prd(self):
        """测试最小 PRD 不崩溃"""
        report = self.analyzer.analyze(MINIMAL_PRD)
        self.assertIsNotNone(report)
        self.assertGreater(len(report.tasks), 0)

    def test_task_ids_unique(self):
        """测试任务 ID 唯一性"""
        report = self.analyzer.analyze(SAMPLE_PRD)
        ids = [t.id for t in report.tasks]
        self.assertEqual(len(ids), len(set(ids)))


class TestReportFormatter(unittest.TestCase):

    def setUp(self):
        self.analyzer = PRDAnalyzer()
        self.report = self.analyzer.analyze(SAMPLE_PRD)
        self.formatter = ReportFormatter()

    def test_markdown_output_structure(self):
        """测试 Markdown 输出结构"""
        md = self.formatter.to_markdown(self.report)
        self.assertIn('# 📋 PRD 任务拆解报告', md)
        self.assertIn('## 📊 总览', md)
        self.assertIn('## ✅ 任务清单', md)
        self.assertIn('## ⚠️ PRD 问题清单', md)

    def test_markdown_contains_tasks(self):
        """测试 Markdown 包含任务内容"""
        md = self.formatter.to_markdown(self.report)
        for task in self.report.tasks[:3]:
            self.assertIn(task.id, md)

    def test_csv_output(self):
        """测试 CSV 输出"""
        csv_content = self.formatter.to_csv(self.report)
        lines = csv_content.strip().split('\n')
        self.assertGreater(len(lines), 1)  # 至少有表头和一行数据
        self.assertIn('任务ID', lines[0])
        self.assertIn('所属模块', lines[0])

    def test_csv_row_count(self):
        """测试 CSV 行数与任务数一致"""
        csv_content = self.formatter.to_csv(self.report)
        lines = [l for l in csv_content.strip().split('\n') if l]
        self.assertEqual(len(lines) - 1, len(self.report.tasks))  # 减去表头

    def test_json_output(self):
        """测试 JSON 输出"""
        import json
        json_str = self.formatter.to_json(self.report)
        data = json.loads(json_str)
        self.assertIn('prd_title', data)
        self.assertIn('tasks', data)
        self.assertIn('summary', data)
        self.assertEqual(len(data['tasks']), len(self.report.tasks))

    def test_json_is_valid(self):
        """测试 JSON 格式合法"""
        import json
        json_str = self.formatter.to_json(self.report)
        try:
            json.loads(json_str)
        except json.JSONDecodeError:
            self.fail('JSON 输出格式不合法')


class TestIntegration(unittest.TestCase):

    def test_full_example_prd(self):
        """集成测试：分析完整示例 PRD"""
        example = Path(__file__).parent.parent / 'example_prd.md'
        if not example.exists():
            self.skipTest('example_prd.md 不存在')

        analyzer = PRDAnalyzer()
        report = analyzer.analyze(example.read_text(encoding='utf-8'))

        self.assertGreater(len(report.modules), 3)
        self.assertGreater(len(report.tasks), 5)
        self.assertGreater(report.summary['total_hours'], 0)

        # 应该检测到第三方接口风险
        all_risks = [r for t in report.tasks for r in t.risks]
        self.assertGreater(len(all_risks), 0)

        # 三种格式都能正常输出
        formatter = ReportFormatter()
        self.assertTrue(len(formatter.to_markdown(report)) > 100)
        self.assertTrue(len(formatter.to_csv(report)) > 50)
        self.assertTrue(len(formatter.to_json(report)) > 100)


def run_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPRDAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestReportFormatter))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print('\n' + '=' * 60)
    print(f'测试总数: {result.testsRun}')
    print(f'成功: {result.testsRun - len(result.failures) - len(result.errors)}')
    print(f'失败: {len(result.failures)}')
    print(f'错误: {len(result.errors)}')
    print('=' * 60)
    return result.wasSuccessful()


if __name__ == '__main__':
    sys.exit(0 if run_tests() else 1)

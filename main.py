#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRD 智能任务拆解器
输入一份中文产品需求文档，自动输出开发任务清单、工时估算、依赖关系、风险识别
"""

import re
import json
import csv
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class TaskType(Enum):
    FRONTEND = "前端"
    BACKEND = "后端"
    DATABASE = "数据库"
    TEST = "测试"
    DEVOPS = "运维/部署"
    DESIGN = "UI/设计"
    UNKNOWN = "待确认"


class Priority(Enum):
    P0 = "P0-紧急"
    P1 = "P1-高"
    P2 = "P2-中"
    P3 = "P3-低"


@dataclass
class Task:
    """单个开发任务"""
    id: str
    module: str
    title: str
    description: str
    task_type: str
    priority: str
    estimate_hours: float
    depends_on: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


@dataclass
class PRDIssue:
    """PRD 中发现的问题"""
    severity: str   # critical / warning / info
    location: str
    issue: str
    suggestion: str


@dataclass
class AnalysisReport:
    """完整分析报告"""
    prd_title: str
    analyzed_at: str
    modules: List[str]
    tasks: List[Task]
    issues: List[PRDIssue]
    

    summary: Dict = field(default_factory=dict)


# ─────────────────────────────────────────────
# 关键词库
# ─────────────────────────────────────────────

FRONTEND_KEYWORDS = [
    '页面', '界面', '前端', 'UI', 'UX', '展示', '显示', '渲染', '组件',
    '按钮', '表单', '列表', '弹窗', '导航', '菜单', '样式', 'CSS', 'H5',
    '移动端', 'PC端', '响应式', '动画', '交互', '输入框', '下拉', '上传',
]

BACKEND_KEYWORDS = [
    '接口', 'API', '后端', '服务', '逻辑', '计算', '处理', '校验', '验证',
    '权限', '鉴权', '认证', 'token', 'JWT', '缓存', 'Redis', '队列',
    '消息', '推送', '定时任务', '调度', '第三方', '对接', '集成',
]

DATABASE_KEYWORDS = [
    '数据库', '表结构', '字段', '存储', '查询', '索引', '迁移', 'SQL',
    '数据模型', 'ORM', '关联', '外键', '数据', '记录', '持久化',
]

TEST_KEYWORDS = [
    '测试', '单测', '集成测试', '压测', '性能测试', '用例', 'QA',
    '验收', '回归', '自动化测试', 'E2E',
]

DEVOPS_KEYWORDS = [
    '部署', '上线', '运维', 'Docker', 'K8s', 'CI/CD', '监控', '日志',
    '告警', '扩容', '备份', '容灾', '域名', 'HTTPS', '证书', 'CDN',
]

DESIGN_KEYWORDS = [
    '设计', '原型', '视觉', '切图', '标注', 'Figma', 'Sketch', '图标',
    '配色', '字体', '间距', '布局',
]

# 模糊/风险词汇
VAGUE_WORDS = [
    '尽快', '适当', '合理', '简单', '方便', '友好', '智能', '自动',
    '灵活', '高效', '稳定', '安全', '完善', '优化', '等', '等等',
    '类似', '参考', '大概', '可能', '也许', '暂定', '待定', 'TBD',
]

RISK_PATTERNS = [
    (r'第三方|外部系统|对接', '依赖外部系统，需提前确认接口文档和联调时间'),
    (r'实时|毫秒|高并发|大量用户', '存在性能要求，需提前做容量规划和压测'),
    (r'支付|金额|钱|财务|账单', '涉及资金安全，需严格测试和审计'),
    (r'权限|角色|鉴权|隐私|敏感', '涉及安全权限，需安全评审'),
    (r'迁移|历史数据|存量', '涉及数据迁移，需制定回滚方案'),
    (r'兼容|旧版本|老数据', '存在兼容性风险，需明确兼容范围'),
]

# 工时估算基准（小时）
ESTIMATE_BASE = {
    TaskType.FRONTEND.value: {'simple': 4, 'medium': 8, 'complex': 16},
    TaskType.BACKEND.value:  {'simple': 4, 'medium': 8, 'complex': 20},
    TaskType.DATABASE.value: {'simple': 2, 'medium': 4, 'complex': 8},
    TaskType.TEST.value:     {'simple': 2, 'medium': 4, 'complex': 8},
    TaskType.DEVOPS.value:   {'simple': 2, 'medium': 4, 'complex': 8},
    TaskType.DESIGN.value:   {'simple': 4, 'medium': 8, 'complex': 16},
    TaskType.UNKNOWN.value:  {'simple': 4, 'medium': 8, 'complex': 16},
}


# ─────────────────────────────────────────────
# 核心分析器
# ─────────────────────────────────────────────

class PRDAnalyzer:
    """PRD 智能分析器"""

    def __init__(self):
        self.task_counter = 0

    def analyze(self, prd_text: str) -> AnalysisReport:
        """主入口：分析 PRD 文本，返回完整报告"""
        self.task_counter = 0
        title = self._extract_title(prd_text)
        modules = self._extract_modules(prd_text)
        tasks = self._extract_tasks(prd_text, modules)
        tasks = self._infer_dependencies(tasks)
        issues = self._detect_prd_issues(prd_text, tasks)
        summary = self._build_summary(tasks, issues)

        return AnalysisReport(
            prd_title=title,
            analyzed_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            modules=modules,
            tasks=tasks,
            issues=issues,
            summary=summary,
        )

    # ── 标题提取 ──────────────────────────────

    def _extract_title(self, text: str) -> str:
        """提取 PRD 标题"""
        for line in text.split('\n')[:10]:
            line = line.strip().lstrip('#').strip()
            if line and len(line) < 60:
                return line
        return '未命名需求文档'

    # ── 模块提取 ──────────────────────────────

    def _extract_modules(self, text: str) -> List[str]:
        """识别 PRD 中的功能模块"""
        modules = []
        # 匹配二级/三级标题作为模块
        patterns = [
            r'^#{1,3}\s+(.+)',          # Markdown 标题
            r'^[一二三四五六七八九十]+[、.．]\s*(.+)',  # 中文序号
            r'^\d+[、.．]\s*(.+)',       # 数字序号
            r'^【(.+?)】',               # 【模块名】
        ]
        seen = set()
        for line in text.split('\n'):
            line = line.strip()
            for pattern in patterns:
                m = re.match(pattern, line)
                if m:
                    name = m.group(1).strip().rstrip('：:')
                    # 过滤掉太短或明显是非模块的标题
                    if 2 <= len(name) <= 20 and name not in seen:
                        # 排除常见非功能性章节
                        skip = ['背景', '目标', '概述', '说明', '附录', '修订', '版本', '术语', '参考']
                        if not any(s in name for s in skip):
                            modules.append(name)
                            seen.add(name)
                    break
        return modules if modules else ['核心功能']

    # ── 任务提取 ──────────────────────────────

    def _extract_tasks(self, text: str, modules: List[str]) -> List[Task]:
        """从 PRD 中提取开发任务，最多提取 300 个"""
        tasks = []
        sections = self._split_by_module(text, modules)

        for module, section_text in sections.items():
            module_tasks = self._parse_section_tasks(module, section_text)
            tasks.extend(module_tasks)
            if len(tasks) >= 300:
                tasks = tasks[:300]
                break

        # 如果没有解析出任务，做兜底处理
        if not tasks:
            tasks = self._fallback_task_extraction(text)

        return tasks

    def _split_by_module(self, text: str, modules: List[str]) -> Dict[str, str]:
        """按模块切分文本"""
        result = {}
        lines = text.split('\n')
        current_module = '通用'
        current_lines = []

        for line in lines:
            matched = False
            for module in modules:
                if module in line and (line.startswith('#') or
                        re.match(r'^[一二三四五六七八九十\d]+[、.．]', line) or
                        line.startswith('【')):
                    if current_lines:
                        result[current_module] = '\n'.join(current_lines)
                    current_module = module
                    current_lines = [line]
                    matched = True
                    break
            if not matched:
                current_lines.append(line)

        if current_lines:
            result[current_module] = '\n'.join(current_lines)

        return result

    def _parse_section_tasks(self, module: str, text: str) -> List[Task]:
        """解析单个模块章节中的任务"""
        tasks = []
        # 提取功能点：列表项、子标题、动词短语
        feature_patterns = [
            r'^[-*•]\s+(.+)',
            r'^\d+\.\s+(.+)',
            r'^[a-zA-Z]\.\s+(.+)',
            r'支持(.{2,20})[，。；\n]',
            r'提供(.{2,20})[，。；\n]',
            r'实现(.{2,20})[，。；\n]',
            r'允许(.{2,20})[，。；\n]',
            r'用户可以(.{2,20})[，。；\n]',
            r'系统(?:需要|应该|必须)(.{2,20})[，。；\n]',
            r'需要(.{2,20})[，。；\n]',
            r'数据库(?:需要|应该)?(.{2,20})[，。；\n]',
            r'展示(.{2,20})[，。；\n]',
        ]

        seen_titles = set()
        for line in text.split('\n'):
            line = line.strip()
            if not line or len(line) < 4:
                continue
            for pattern in feature_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    match = match.strip().rstrip('，。；、')
                    if len(match) < 4 or match in seen_titles:
                        continue
                    seen_titles.add(match)
                    task = self._build_task(module, match, text)
                    tasks.append(task)
                    break

        return tasks

    def _build_task(self, module: str, feature: str, context: str) -> Task:
        """根据功能描述构建任务对象"""
        self.task_counter += 1
        task_id = f'T{self.task_counter:03d}'
        task_type = self._classify_task_type(feature, context)
        complexity = self._estimate_complexity(feature, context)
        estimate = ESTIMATE_BASE[task_type][complexity]
        priority = self._estimate_priority(feature, context)
        acceptance = self._generate_acceptance_criteria(feature, task_type)
        risks = self._detect_task_risks(feature)

        return Task(
            id=task_id,
            module=module,
            title=feature[:40],
            description=f'实现{feature}相关功能',
            task_type=task_type,
            priority=priority,
            estimate_hours=estimate,
            acceptance_criteria=acceptance,
            risks=risks,
        )

    def _fallback_task_extraction(self, text: str) -> List[Task]:
        """兜底：按段落提取任务"""
        tasks = []
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 20]
        for i, para in enumerate(paragraphs[:10]):
            first_line = para.split('\n')[0].strip().lstrip('#').strip()
            if first_line:
                task = self._build_task('核心功能', first_line[:40], para)
                tasks.append(task)
        return tasks

    # ── 分类 & 估算 ───────────────────────────

    def _classify_task_type(self, feature: str, context: str) -> str:
        """识别任务类型：优先用 feature 本身，再参考上下文"""
        scores = {t.value: 0 for t in TaskType}

        kw_map = [
            (FRONTEND_KEYWORDS, TaskType.FRONTEND.value,  1),
            (BACKEND_KEYWORDS,  TaskType.BACKEND.value,   1),
            (DATABASE_KEYWORDS, TaskType.DATABASE.value,  2),
            (TEST_KEYWORDS,     TaskType.TEST.value,      2),
            (DEVOPS_KEYWORDS,   TaskType.DEVOPS.value,    2),
            (DESIGN_KEYWORDS,   TaskType.DESIGN.value,    2),
        ]

        # 第一轮：只看 feature 本身（权重 x3）
        for keywords, ttype, weight in kw_map:
            for kw in keywords:
                if kw.lower() in feature.lower():
                    scores[ttype] += weight * 3

        # 如果 feature 本身已经有明确信号，直接返回
        best = max(scores, key=lambda k: scores[k])
        if scores[best] > 0:
            return best

        # 第二轮：参考上下文
        for keywords, ttype, weight in kw_map:
            for kw in keywords:
                if kw.lower() in context.lower():
                    scores[ttype] += weight

        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else TaskType.UNKNOWN.value

    def _estimate_complexity(self, feature: str, context: str) -> str:
        """估算任务复杂度"""
        complex_signals = ['复杂', '多种', '多个', '批量', '导入', '导出',
                           '报表', '统计', '图表', '权限', '工作流', '审批',
                           '第三方', '对接', '实时', '并发', '算法']
        simple_signals = ['简单', '基础', '基本', '查看', '展示', '列表',
                          '详情', '跳转', '提示', '文案']

        text = feature + context
        complex_count = sum(1 for s in complex_signals if s in text)
        simple_count = sum(1 for s in simple_signals if s in text)

        if complex_count >= 2:
            return 'complex'
        elif simple_count >= 2 or len(feature) < 8:
            return 'simple'
        return 'medium'

    def _estimate_priority(self, feature: str, context: str) -> str:
        """估算优先级"""
        p0_signals = ['核心', '主流程', '必须', '关键', '支付', '登录', '注册', '安全']
        p1_signals = ['重要', '主要', '基础功能', '用户', '常用']
        p3_signals = ['可选', '后续', '优化', '增强', '扩展', '未来']

        text = feature + context
        if any(s in text for s in p0_signals):
            return Priority.P0.value
        if any(s in text for s in p3_signals):
            return Priority.P3.value
        if any(s in text for s in p1_signals):
            return Priority.P1.value
        return Priority.P2.value

    def _generate_acceptance_criteria(self, feature: str, task_type: str) -> List[str]:
        """自动生成验收标准"""
        criteria = [f'功能实现：{feature}功能正常运行']

        if task_type == TaskType.FRONTEND.value:
            criteria += [
                '界面与设计稿一致，误差 ≤ 2px',
                '在 Chrome/Safari/Firefox 最新版本正常显示',
                '移动端适配正常（如涉及）',
            ]
        elif task_type == TaskType.BACKEND.value:
            criteria += [
                '接口返回正确的数据结构和状态码',
                '异常情况有明确的错误提示',
                '接口响应时间 ≤ 500ms（正常负载下）',
            ]
        elif task_type == TaskType.DATABASE.value:
            criteria += [
                '数据库表结构符合设计文档',
                '索引设计合理，查询性能达标',
                '数据迁移脚本可回滚',
            ]
        elif task_type == TaskType.TEST.value:
            criteria += [
                '测试用例覆盖主流程和异常流程',
                '测试通过率 100%',
            ]
        return criteria

    def _detect_task_risks(self, feature: str) -> List[str]:
        """检测单个任务的风险"""
        risks = []
        for pattern, risk in RISK_PATTERNS:
            if re.search(pattern, feature):
                risks.append(risk)
        return risks

    # ── 依赖推断 ──────────────────────────────

    def _infer_dependencies(self, tasks: List[Task]) -> List[Task]:
        """推断任务间的依赖关系"""
        # 规则：前端任务依赖同模块的后端任务；测试任务依赖同模块的开发任务
        module_backend = {}   # module -> [task_id]
        module_db = {}        # module -> [task_id]
        module_dev = {}       # module -> [task_id]

        for task in tasks:
            m = task.module
            if task.task_type == TaskType.BACKEND.value:
                module_backend.setdefault(m, []).append(task.id)
            if task.task_type == TaskType.DATABASE.value:
                module_db.setdefault(m, []).append(task.id)
            if task.task_type in (TaskType.FRONTEND.value, TaskType.BACKEND.value):
                module_dev.setdefault(m, []).append(task.id)

        for task in tasks:
            m = task.module
            if task.task_type == TaskType.FRONTEND.value:
                task.depends_on = module_backend.get(m, [])[:2]
            elif task.task_type == TaskType.BACKEND.value:
                task.depends_on = module_db.get(m, [])[:2]
            elif task.task_type == TaskType.TEST.value:
                task.depends_on = module_dev.get(m, [])[:3]

        return tasks

    # ── PRD 问题检测 ──────────────────────────

    def _detect_prd_issues(self, text: str, tasks: List[Task]) -> List[PRDIssue]:
        """检测 PRD 文档本身的问题"""
        issues = []
        lines = text.split('\n')

        # 1. 检测模糊词汇
        for i, line in enumerate(lines, 1):
            for vague in VAGUE_WORDS:
                if vague in line:
                    issues.append(PRDIssue(
                        severity='warning',
                        location=f'第 {i} 行',
                        issue=f'使用了模糊词汇「{vague}」',
                        suggestion=f'请将「{vague}」替换为可量化的描述，例如具体数值、明确行为或可验证的标准',
                    ))
                    break  # 每行只报一次

        # 2. 检测缺少验收标准的模块
        has_acceptance = bool(re.search(r'验收|AC:|acceptance|通过条件', text, re.IGNORECASE))
        if not has_acceptance:
            issues.append(PRDIssue(
                severity='critical',
                location='全文',
                issue='PRD 中未发现验收标准',
                suggestion='建议为每个功能模块添加明确的验收标准（AC），避免开发和测试理解偏差',
            ))

        # 3. 检测缺少异常流程描述
        has_error_flow = bool(re.search(r'异常|错误|失败|边界|容错|降级', text))
        if not has_error_flow:
            issues.append(PRDIssue(
                severity='warning',
                location='全文',
                issue='PRD 中未描述异常/错误处理流程',
                suggestion='建议补充各功能的异常场景处理，如网络失败、数据为空、权限不足等',
            ))

        # 4. 检测缺少性能指标
        has_perf = bool(re.search(r'性能|响应时间|并发|QPS|TPS|毫秒|秒内', text))
        if not has_perf:
            issues.append(PRDIssue(
                severity='info',
                location='全文',
                issue='PRD 中未定义性能指标',
                suggestion='建议明确关键接口的响应时间要求和并发量预期',
            ))

        # 5. 检测任务中的风险
        for task in tasks:
            for risk in task.risks:
                issues.append(PRDIssue(
                    severity='warning',
                    location=f'任务 {task.id}：{task.title}',
                    issue=risk,
                    suggestion='请在开发前与相关方确认，并制定应对方案',
                ))

        return issues

    # ── 汇总统计 ──────────────────────────────

    def _build_summary(self, tasks: List[Task], issues: List[PRDIssue]) -> Dict:
        """生成汇总统计"""
        total_hours = sum(t.estimate_hours for t in tasks)
        by_type = {}
        by_priority = {}
        by_module = {}

        for task in tasks:
            by_type[task.task_type] = by_type.get(task.task_type, 0) + 1
            by_priority[task.priority] = by_priority.get(task.priority, 0) + 1
            by_module[task.module] = by_module.get(task.module, {'count': 0, 'hours': 0})
            by_module[task.module]['count'] += 1
            by_module[task.module]['hours'] += task.estimate_hours

        issue_severity = {}
        for issue in issues:
            issue_severity[issue.severity] = issue_severity.get(issue.severity, 0) + 1

        # 工作日估算（按每天8小时，并行系数0.6）
        working_days = round(total_hours / 8 / max(len(set(t.task_type for t in tasks)), 1) / 0.6, 1)

        return {
            'total_tasks': len(tasks),
            'total_hours': total_hours,
            'estimated_working_days': working_days,
            'by_type': by_type,
            'by_priority': by_priority,
            'by_module': by_module,
            'total_issues': len(issues),
            'issue_severity': issue_severity,
        }


# ─────────────────────────────────────────────
# 输出格式化
# ─────────────────────────────────────────────

class ReportFormatter:
    """多格式报告输出器"""

    @staticmethod
    def to_markdown(report: AnalysisReport) -> str:
        """输出 Markdown 格式报告"""
        s = report.summary
        md = f"""# 📋 PRD 任务拆解报告

> **需求文档**：{report.prd_title}
> **分析时间**：{report.analyzed_at}

---

## 📊 总览

| 指标 | 数值 |
|------|------|
| 识别模块数 | {len(report.modules)} 个 |
| 拆解任务数 | {s['total_tasks']} 个 |
| 总工时估算 | {s['total_hours']} 小时 |
| 预计工期 | {s['estimated_working_days']} 个工作日 |
| PRD 问题数 | {s['total_issues']} 个 |

### 任务类型分布
"""
        type_emoji = {
            '前端': '🖥️', '后端': '⚙️', '数据库': '🗄️',
            '测试': '🧪', '运维/部署': '🚀', 'UI/设计': '🎨', '待确认': '❓'
        }
        for ttype, count in s['by_type'].items():
            emoji = type_emoji.get(ttype, '📌')
            hours = sum(t.estimate_hours for t in report.tasks if t.task_type == ttype)
            md += f'- {emoji} **{ttype}**：{count} 个任务，共 {hours}h\n'

        md += '\n### 优先级分布\n'
        priority_emoji = {'P0-紧急': '🔴', 'P1-高': '🟠', 'P2-中': '🟡', 'P3-低': '🔵'}
        for pri, count in sorted(s['by_priority'].items()):
            emoji = priority_emoji.get(pri, '⚪')
            md += f'- {emoji} **{pri}**：{count} 个\n'

        md += '\n---\n\n## 📦 模块概览\n\n'
        md += '| 模块 | 任务数 | 工时 |\n|------|--------|------|\n'
        for mod, info in s['by_module'].items():
            md += f'| {mod} | {info["count"]} | {info["hours"]}h |\n'

        md += '\n---\n\n## ✅ 任务清单\n\n'
        current_module = None
        for task in report.tasks:
            if task.module != current_module:
                current_module = task.module
                md += f'\n### 📁 {task.module}\n\n'

            dep_str = '、'.join(task.depends_on) if task.depends_on else '无'
            md += f'#### [{task.id}] {task.title}\n\n'
            md += f'- **类型**：{task.task_type}\n'
            md += f'- **优先级**：{task.priority}\n'
            md += f'- **工时估算**：{task.estimate_hours}h\n'
            md += f'- **依赖任务**：{dep_str}\n'
            md += f'- **描述**：{task.description}\n'

            if task.acceptance_criteria:
                md += '- **验收标准**：\n'
                for ac in task.acceptance_criteria:
                    md += f'  - {ac}\n'

            if task.risks:
                md += '- **⚠️ 风险提示**：\n'
                for risk in task.risks:
                    md += f'  - {risk}\n'
            md += '\n'

        md += '---\n\n## ⚠️ PRD 问题清单\n\n'
        if not report.issues:
            md += '_未发现明显问题，PRD 质量良好。_\n'
        else:
            sev_emoji = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}
            sev_label = {'critical': '严重', 'warning': '警告', 'info': '提示'}
            for i, issue in enumerate(report.issues, 1):
                emoji = sev_emoji.get(issue.severity, '⚪')
                label = sev_label.get(issue.severity, issue.severity)
                md += f'#### {i}. {emoji} [{label}] {issue.location}\n\n'
                md += f'**问题**：{issue.issue}\n\n'
                md += f'**建议**：{issue.suggestion}\n\n'

        md += '---\n\n## 🗓️ 建议排期\n\n'
        md += '```\n'
        md += 'P0 任务（核心主流程）→ 第 1 周优先完成\n'
        md += 'P1 任务（重要功能）  → 第 2 周跟进\n'
        md += 'P2 任务（常规功能）  → 第 3 周推进\n'
        md += 'P3 任务（优化增强）  → 迭代后续版本\n'
        md += '```\n\n'
        md += '_报告由 PRD 智能任务拆解器自动生成_\n'
        return md

    @staticmethod
    def to_csv(report: AnalysisReport) -> str:
        """输出飞书/钉钉多维表格兼容的 CSV"""
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['任务ID', '所属模块', '任务标题', '任务类型',
                         '优先级', '工时(h)', '依赖任务', '描述', '验收标准', '风险'])
        for task in report.tasks:
            writer.writerow([
                task.id, task.module, task.title, task.task_type,
                task.priority, task.estimate_hours,
                ' | '.join(task.depends_on),
                task.description,
                ' | '.join(task.acceptance_criteria),
                ' | '.join(task.risks),
            ])
        return output.getvalue()

    @staticmethod
    def to_json(report: AnalysisReport) -> str:
        """输出 JSON 格式"""
        data = {
            'prd_title': report.prd_title,
            'analyzed_at': report.analyzed_at,
            'summary': report.summary,
            'modules': report.modules,
            'tasks': [asdict(t) for t in report.tasks],
            'issues': [asdict(i) for i in report.issues],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# 主程序入口
# ─────────────────────────────────────────────

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description='PRD 智能任务拆解器 - 将产品需求文档自动拆解为开发任务清单',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py example_prd.md
  python main.py my_prd.md --format csv
  python main.py my_prd.md --format json --output tasks.json
        """
    )
    parser.add_argument('prd_file', help='PRD 文件路径（支持 .md / .txt）')
    parser.add_argument('--format', choices=['markdown', 'csv', 'json'],
                        default='markdown', help='输出格式（默认 markdown）')
    parser.add_argument('--output', help='输出文件路径（不指定则打印到终端）')
    args = parser.parse_args()

    prd_path = Path(args.prd_file)
    if not prd_path.exists():
        print(f'❌ 文件不存在：{args.prd_file}')
        sys.exit(1)

    prd_text = prd_path.read_text(encoding='utf-8')
    if len(prd_text.strip()) < 50:
        print('❌ PRD 内容过短，请检查文件内容')
        sys.exit(1)

    print(f'🔍 正在分析：{prd_path.name} ...')
    analyzer = PRDAnalyzer()
    report = analyzer.analyze(prd_text)

    # 格式化输出
    formatter = ReportFormatter()
    if args.format == 'csv':
        content = formatter.to_csv(report)
        default_ext = '.csv'
    elif args.format == 'json':
        content = formatter.to_json(report)
        default_ext = '.json'
    else:
        content = formatter.to_markdown(report)
        default_ext = '.md'

    # 写入文件或打印
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = Path(f'task_report_{prd_path.stem}_{ts}{default_ext}')

    output_path.write_text(content, encoding='utf-8')

    s = report.summary
    print(f'\n✅ 分析完成！')
    print(f'📦 识别模块：{len(report.modules)} 个')
    print(f'📋 拆解任务：{s["total_tasks"]} 个')
    print(f'⏱️  总工时估算：{s["total_hours"]} 小时（约 {s["estimated_working_days"]} 个工作日）')
    print(f'⚠️  PRD 问题：{s["total_issues"]} 个')
    print(f'📄 报告已保存：{output_path}')

    # 打印问题摘要
    if report.issues:
        critical = [i for i in report.issues if i.severity == 'critical']
        if critical:
            print(f'\n🔴 发现 {len(critical)} 个严重问题，请优先处理：')
            for issue in critical[:3]:
                print(f'   • [{issue.location}] {issue.issue}')


if __name__ == '__main__':
    main()

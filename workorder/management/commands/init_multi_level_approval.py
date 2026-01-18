from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = '初始化多级审核系统的默认数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-existing',
            action='store_true',
            help='重置已存在的审核工作流数据'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制执行（跳过确认）'
        )

    def handle(self, *args, **options):
        reset_existing = options['reset_existing']
        force = options['force']
        
        if not force:
            self.stdout.write("⚠️  这将删除所有现有的审核工作流数据并重新创建。")
            response = input("确认继续执行吗？(y/N): ")
            if response.lower() != 'y':
                self.stdout.write("操作已取消。")
                return
        
        self.stdout.write("🚀 开始初始化多级审核系统...")
        
        with transaction.atomic():
            if reset_existing:
                self._reset_existing_workflows()
            
            self._create_default_workflows()
            self._create_default_rules()
        
        self.stdout.write("✅ 多级审核系统初始化完成")

    def _reset_existing_workflows(self):
        """重置现有的审核工作流数据"""
        from ..models.multi_level_approval import ApprovalWorkflow, ApprovalStep, ApprovalRule
        
        # 删除所有现有的工作流和步骤
        self.stdout.write("🗑️  清理现有审核工作流数据...")
        
        ApprovalStep.objects.all().delete()
        ApprovalRule.objects.all().delete()
        
        # 重置WorkOrder模型中的相关字段
        from ..models.core import WorkOrder
        
        updated_count = WorkOrder.objects.filter(
            multi_level_approval_enabled=True
        ).update(multi_level_approval_enabled=False)
        
        self.stdout.write(f"   - 重置了{updated_count}个施工单的多级审核状态")

    def _create_default_workflows(self):
        """创建默认审核工作流"""
        from ..models.multi_level_approval import ApprovalWorkflow, MultiLevelApprovalService
        
        self.stdout.write("📋 创建默认审核工作流...")
        
        # 简单订单工作流
        simple_workflow = MultiLevelApprovalService.create_default_workflow('simple', self.user)
        self.stdout.write(f"   ✅ 创建简单订单工作流: {simple_workflow.name}")
        
        # 标准订单工作流
        standard_workflow = MultiLevelApprovalService.create_default_workflow('standard', self.user)
        self.stdout.write(f"   ✅ 创建标准订单工作流: {standard_workflow.name}")
        
        # 复杂订单工作流
        complex_workflow = MultiLevelApprovalService.create_default_workflow('complex', self.user)
        self.stdout.write(f"   ✅ 创建复杂订单工作流: {complex_workflow.name}")
        
        # 紧急订单工作流
        urgent_workflow = MultiLevelApprovalService.create_default_workflow('urgent', self.user)
        self.stdout.write(f"   ✅ 创建紧急订单工作流: {urgent_workflow.name}")
        
        self.stdout.write("   ✅ 默认审核工作流创建完成")

    def _create_default_rules(self):
        """创建默认审核规则"""
        from ..models.multi_level_approval import ApprovalRule
        
        self.stdout.write("📋 创建默认审核规则...")
        
        # 金额阈值规则
        simple_amount_rule = ApprovalRule.objects.create(
            workflow=ApprovalWorkflow.objects.get(workflow_type='simple'),
            rule_type='amount_threshold',
            rule_name='简单订单金额阈值',
            conditions={
                'operator': 'gte',
                'field': 'total_amount',
                'value': 10000
            },
            actions={
                'escalate': True,
                'require_reason': True
            }
        )
        self.stdout.write(f"   ✅ 创建简单订单金额阈值规则: {simple_amount_rule.rule_name}")
        
        standard_amount_rule = ApprovalRule.objects.create(
            workflow=ApprovalWorkflow.objects.get(workflow_type='standard'),
            rule_type='amount_threshold',
            rule_name='标准订单金额阈值',
            conditions={
                'operator': 'gte',
                'field': 'total_amount',
                'value': 50000
            },
            actions={
                'escalate': True,
                'require_reason': True
            }
        )
        self.stdout.write(f"   ✅ 创建标准订单金额阈值规则: {standard_amount_rule.rule_name}")
        
        # 复杂订单金额规则
        complex_amount_rule = ApprovalRule.objects.create(
            workflow=ApprovalWorkflow.objects.get(workflow_type='complex'),
            rule_type='amount_threshold',
            rule_name='复杂订单金额阈值',
            conditions={
                'operator': 'gte',
                'field': 'total_amount',
                'value': 100000
            },
            actions={
                'escalate': True,
                'require_reason': True
            }
        )
        self.stdout.write(f"   ✅ 创建复杂订单金额阈值规则: {complex_amount_rule.rule_name}")
        
        # 优先级规则
        priority_rules = [
            {
                'workflow_type': 'simple',
                'rule_type': 'priority_match',
                'rule_name': '简单订单-仅普通优先级',
                'conditions': {
                    'field': 'priority',
                    'values': ['low', 'normal']
                },
                'actions': {
                    'escalate': True,
                    'require_reason': False
                }
            },
            {
                'workflow_type': 'standard',
                'rule_type': 'priority_match',
                'rule_name': '标准订单-允许高优先级',
                'conditions': {
                    'field': 'priority',
                    'values': ['low', 'normal', 'high']
                },
                'actions': {
                    'escalate': True,
                    'require_reason': False
                }
            },
            {
                'workflow_type': 'complex',
                'rule_type': 'priority_match',
                'rule_name': '复杂订单-允许紧急优先级',
                'conditions': {
                    'field': 'priority',
                    'values': ['low', 'normal', 'high', 'urgent']
                },
                'actions': {
                    'escalate': False,  # 复杂订单允许所有优先级
                    'require_reason': False
                }
            }
        ]
        
        for rule_data in priority_rules:
            workflow = ApprovalWorkflow.objects.get(workflow_type=rule_data['workflow_type'])
            rule = ApprovalRule.objects.create(
                workflow=workflow,
                rule_type=rule_data['rule_type'],
                rule_name=rule_data['rule_name'],
                conditions=rule_data['conditions'],
                actions=rule_data['actions']
            )
            self.stdout.write(f"   ✅ 创建优先级规则: {rule.rule_name}")
        
        # 客户类型规则（示例）
        customer_type_rule = ApprovalRule.objects.create(
            workflow=ApprovalWorkflow.objects.get(workflow_type='standard'),
            rule_type='customer_type',
            rule_name='重要客户特殊审核',
            conditions={
                'field': 'customer__is_important',
                'value': True
            },
            actions={
                'require_manager_approval': True
            }
        )
        self.stdout.write(f"   ✅ 创建客户类型规则: {customer_type_rule.rule_name}")
        
        self.stdout.write("   ✅ 默认审核规则创建完成")

    def _show_workflows_summary(self):
        """显示工作流摘要"""
        from ..models.multi_level_approval import ApprovalWorkflow
        
        workflows = ApprovalWorkflow.objects.all()
        self.stdout.write("\n📊 审核工作流摘要:")
        
        for workflow in workflows:
            steps_count = workflow.steps.count() if workflow.steps else 0
            status = "✅ 激活" if workflow.is_active else "❌ 未激活"
            
            self.stdout.write(f"  {workflow.name} ({workflow.workflow_type})")
            self.stdout.write(f"    状态: {status}")
            self.stdout.write(f"    步骤数量: {steps_count}")
            
            if workflow.steps:
                self.stdout.write("    步骤:")
                for i, step in enumerate(workflow.steps, 1):
                    self.stdout.write(f"      {i}. {step.get('step_name', 'N/A')}")
                    self.stdout.write(f"         类型: {step.get('step_type', 'N/A')}")
                    self.stdout.write(f"         角色: {step.get('role_filter', [])}")
        
        self.stdout.write("")
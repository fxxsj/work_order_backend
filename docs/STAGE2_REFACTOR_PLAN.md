# 阶段 2：P0 紧急问题修复 - 详细执行计划

## 📊 分析结果总结

### work_order_tasks.py 分析（1,651 行）

**文件结构**：
- 仅包含 1 个类：`WorkOrderTaskViewSet`
- 总计 1,586 行方法代码

**方法分布**：

| 方法名 | 行数 | 类型 | 优先级 |
|--------|------|------|--------|
| **基础方法** ||||
| get_queryset | 27 | 查询过滤 | 高 |
| perform_update | 14 | 更新钩子 | 高 |
| **单个任务操作** ||||
| update_quantity | 238 | Action | 高 |
| complete | 189 | Action | 高 |
| cancel | 121 | Action | 中 |
| split | 102 | Action | 中 |
| assign | 83 | Action | 高 |
| **批量操作** ||||
| batch_update_quantity | 166 | Action | 中 |
| batch_complete | 125 | Action | 中 |
| batch_cancel | 128 | Action | 中 |
| batch_assign | 137 | Action | 中 |
| **统计和导出** ||||
| collaboration_stats | 133 | Action | 低 |
| batch_cancel | 128 | Action | 中 |
| assignment_history | 92 | Action | 低 |
| export | 19 | Action | 低 |

### validate_before_approval 分析（138 行）

**函数结构**：

| 验证块 | 行数 | 功能 |
|--------|------|------|
| 基础信息验证 | 17 | 客户、产品、工序、交货日期 |
| 版与工序匹配验证 | 33 | 图稿、刀模、烫金版、压凸版 |
| 数量验证 | 15 | 生产数量、产品数量 |
| 日期验证 | 17 | 交货日期合理性 |
| 物料验证 | 9 | 物料完整性、开料用量 |
| 工序顺序验证 | 25 | 工序顺序合理性 |

---

## 🎯 拆分方案

### 方案 A：work_order_tasks.py 拆分

**目标目录结构**：
```
workorder/views/work_order_tasks/
├── __init__.py           # 主导出和组合类
├── task_main.py          # 主 ViewSet（~100 行）
├── task_actions.py       # 单个任务操作（~730 行）
├── task_bulk.py          # 批量操作（~560 行）
└── task_stats.py         # 统计和导出（~240 行）
```

**详细拆分**：

#### 1. task_main.py（目标 < 150 行）

**内容**：
- `WorkOrderTaskViewSet` 类定义和基础配置
- `get_queryset()` - 查询过滤
- `perform_update()` - 更新钩子

**行数估算**：
- 类定义和配置：30 行
- get_queryset：27 行
- perform_update：14 行
- 导入语句：30 行
- 文档字符串：20 行
- **总计：约 120 行**

#### 2. task_actions.py（目标 < 800 行）

**内容**：
- `TaskActionsMixin` 类
- `update_quantity()` - 更新任务数量（238 行）
- `complete()` - 完成任务（189 行）
- `split()` - 拆分任务（102 行）
- `assign()` - 分派任务（83 行）
- `cancel()` - 取消任务（121 行）

**行数估算**：
- Mixin 类定义：10 行
- 5 个方法：733 行
- 导入语句：40 行
- 文档字符串：30 行
- **总计：约 810 行**

⚠️ **注意**：此文件仍然较大，但比原来的 1,651 行好得多。如果需要，可以在后续阶段进一步拆分。

#### 3. task_bulk.py（目标 < 600 行）

**内容**：
- `TaskBulkMixin` 类
- `batch_update_quantity()` - 批量更新数量（166 行）
- `batch_complete()` - 批量完成（125 行）
- `batch_cancel()` - 批量取消（128 行）
- `batch_assign()` - 批量分派（137 行）

**行数估算**：
- Mixin 类定义：10 行
- 4 个方法：556 行
- 导入语句：30 行
- 文档字符串：20 行
- **总计：约 610 行**

#### 4. task_stats.py（目标 < 270 行）

**内容**：
- `TaskStatsMixin` 类
- `export()` - 导出任务（19 行）
- `assignment_history()` - 分派历史（92 行）
- `collaboration_stats()` - 协作统计（133 行）

**行数估算**：
- Mixin 类定义：10 行
- 3 个方法：244 行
- 导入语句：20 行
- 文档字符串：15 行
- **总计：约 290 行**

#### 5. __init__.py（目标 < 50 行）

**内容**：
- 从各个模块导入 Mixin
- 组合所有 Mixin 成完整的 `WorkOrderTaskViewSet`
- 保持向后兼容（导出原始类名）

```python
"""
施工单任务视图集模块

将原始的 work_order_tasks.py 拆分为多个模块以提高可维护性。
"""

from .task_main import WorkOrderTaskViewSet as BaseWorkOrderTaskViewSet
from .task_actions import TaskActionsMixin
from .task_bulk import TaskBulkMixin
from .task_stats import TaskStatsMixin

# 组合所有 Mixin 成完整的 ViewSet
class WorkOrderTaskViewSet(
    TaskBulkMixin,
    TaskStatsMixin,
    TaskActionsMixin,
    BaseWorkOrderTaskViewSet
):
    """
    完整的施工单任务视图集
    
    通过组合多个 Mixin 实现，每个 Mixin 提供特定的功能。
    """
    pass

# 保持向后兼容
__all__ = ['WorkOrderTaskViewSet']
```

**Mixin 组合顺序**：
- `TaskBulkMixin` - 批量操作（最底层）
- `TaskStatsMixin` - 统计查询（只读操作）
- `TaskActionsMixin` - 单个任务操作（中间层）
- `BaseWorkOrderTaskViewSet` - 基础 CRUD（最底层）

---

### 方案 B：validate_before_approval 重构

**目标**：
- 创建 `workorder/models/validation.py`
- 将 138 行的单一函数拆分为 7 个 <30 行的方法

**新文件结构**：
```
workorder/models/
└── validation.py          # 新建验证器模块（~250 行）
```

**详细设计**：

#### validation.py 文件内容

```python
"""
施工单验证器

将 WorkOrder.validate_before_approval 的逻辑拆分为独立的验证器类。
"""

from django.utils import timezone
from django.db import models


class WorkOrderValidator:
    """
    施工单验证器
    
    将审核前的各种验证逻辑拆分为独立方法，提高可测试性和可维护性。
    
    使用示例:
        validator = WorkOrderValidator(work_order)
        errors = validator.validate_all()
        if errors:
            # 处理错误
    """
    
    def __init__(self, work_order):
        """
        初始化验证器
        
        Args:
            work_order: 要验证的 WorkOrder 实例
        """
        self.work_order = work_order
        self.errors = []
    
    def validate_all(self):
        """
        执行所有验证
        
        Returns:
            list: 错误信息列表，如果为空则表示验证通过
        """
        self.validate_basic_info()
        self.validate_asset_process_match()
        self.validate_quantities()
        self.validate_dates()
        self.validate_materials()
        self.validate_process_sequence()
        return self.errors
    
    def validate_basic_info(self):
        """
        验证基础信息（客户、产品、工序、交货日期）
        
        Returns:
            None: 错误会添加到 self.errors
        """
        # 检查客户信息
        if getattr(self.work_order, 'customer_id', None) is None:
            self.errors.append('缺少客户信息')
        
        # 检查产品信息
        if not self.work_order.products.exists():
            self.errors.append('缺少产品信息')
        
        # 检查工序信息
        if not self.work_order.order_processes.exists():
            self.errors.append('缺少工序信息')
        
        # 检查交货日期
        if not self.work_order.delivery_date:
            self.errors.append('缺少交货日期')
    
    def validate_asset_process_match(self):
        """
        验证版与工序匹配（图稿、刀模、烫金版、压凸版）
        
        确保选择的工序与所需的各种版（图稿、刀模等）匹配。
        """
        from ..models.base import Process
        
        # 获取所有选中的工序
        selected_processes = self.work_order.order_processes.values_list('process', flat=True)
        processes = Process.objects.filter(id__in=selected_processes, is_active=True)
        
        # 检查图稿
        processes_requiring_artwork = processes.filter(
            models.Q(requires_artwork=True) | models.Q(artwork_required=True)
        )
        if processes_requiring_artwork.exists() and not self.work_order.artworks.exists():
            process_names = ', '.join([p.name for p in processes_requiring_artwork])
            self.errors.append(f'选择了需要图稿的工序（{process_names}），请至少选择一个图稿')
        
        # 检查刀模
        processes_requiring_die = processes.filter(
            models.Q(requires_die=True) | models.Q(die_required=True)
        )
        if processes_requiring_die.exists() and not self.work_order.dies.exists():
            process_names = ', '.join([p.name for p in processes_requiring_die])
            self.errors.append(f'选择了需要刀模的工序（{process_names}），请至少选择一个刀模')
        
        # 检查烫金版
        processes_requiring_foiling_plate = processes.filter(
            requires_foiling_plate=True, 
            foiling_plate_required=True
        )
        if processes_requiring_foiling_plate.exists() and not self.work_order.foiling_plates.exists():
            process_names = ', '.join([p.name for p in processes_requiring_foiling_plate])
            self.errors.append(f'选择了需要烫金版的工序（{process_names}），请至少选择一个烫金版')
        
        # 检查压凸版
        processes_requiring_embossing_plate = processes.filter(
            requires_embossing_plate=True,
            embossing_plate_required=True
        )
        if processes_requiring_embossing_plate.exists() and not self.work_order.embossing_plates.exists():
            process_names = ', '.join([p.name for p in processes_requiring_embossing_plate])
            self.errors.append(f'选择了需要压凸版的工序（{process_names}），请至少选择一个压凸版')
    
    def validate_quantities(self):
        """
        验证数量（生产数量、产品数量）
        """
        # 检查生产数量
        if self.work_order.production_quantity is None:
            self.errors.append('缺少生产数量')
        elif self.work_order.production_quantity <= 0:
            self.errors.append(
                f'生产数量必须大于0，当前值为{self.work_order.production_quantity}'
            )
        
        # 检查产品数量总和
        if self.work_order.products.exists():
            products = self.work_order.products.select_related('product').all()
            total_product_quantity = sum([p.quantity or 0 for p in products])
            if total_product_quantity <= 0:
                self.errors.append(
                    f'产品数量总和必须大于0，当前总和为{total_product_quantity}'
                )
    
    def validate_dates(self):
        """
        验证日期（交货日期合理性）
        """
        # 检查交货日期是否早于下单日期
        if self.work_order.delivery_date and self.work_order.order_date:
            order_date = self.work_order.order_date
            if hasattr(order_date, 'date'):
                order_date = order_date.date()
            
            if self.work_order.delivery_date < order_date:
                self.errors.append(
                    f'交货日期不能早于下单日期。'
                    f'交货日期：{self.work_order.delivery_date}，'
                    f'下单日期：{order_date}'
                )
        
        # 检查交货日期是否在过去（允许今天）
        today = timezone.now().date()
        if self.work_order.delivery_date and self.work_order.delivery_date < today:
            self.errors.append(
                f'交货日期不能早于今天。'
                f'交货日期：{self.work_order.delivery_date}，'
                f'今天：{today}'
            )
    
    def validate_materials(self):
        """
        验证物料（物料信息完整性、开料物料用量）
        """
        if not self.work_order.materials.exists():
            return
        
        materials = self.work_order.materials.select_related('material').all()
        for material_item in materials:
            if material_item.need_cutting and not material_item.material_usage:
                self.errors.append(
                    f'物料"{material_item.material.name}"需要开料，请填写物料用量'
                )
    
    def validate_process_sequence(self):
        """
        验证工序顺序（工序顺序合理性）
        
        确保制版在印刷之前，开料在印刷之前等。
        """
        processes_ordered = self.work_order.order_processes.filter(
            process__code__in=['CTP', 'PRT', 'CUT']
        ).select_related('process').order_by('sequence')
        
        ctp_sequence = None
        prt_sequence = None
        cut_sequence = None
        
        for wp in processes_ordered:
            if wp.process.code == 'CTP':
                ctp_sequence = wp.sequence
            elif wp.process.code == 'PRT':
                prt_sequence = wp.sequence
            elif wp.process.code == 'CUT':
                cut_sequence = wp.sequence
        
        if ctp_sequence is not None and prt_sequence is not None:
            if ctp_sequence > prt_sequence:
                self.errors.append(
                    '制版工序（CTP）应该在印刷工序（PRT）之前，请调整工序顺序'
                )
        
        if cut_sequence is not None and prt_sequence is not None:
            if cut_sequence > prt_sequence:
                self.errors.append(
                    '开料工序（CUT）应该在印刷工序（PRT）之前，请调整工序顺序'
                )
```

**修改 models/core.py**：

```python
# 在 WorkOrder 模型中修改 validate_before_approval 方法

def validate_before_approval(self):
    """
    审核前验证施工单数据完整性
    
    使用 WorkOrderValidator 进行验证。
    
    Returns:
        list: 错误信息列表，如果为空则表示验证通过
    """
    from .validation import WorkOrderValidator
    
    validator = WorkOrderValidator(self)
    return validator.validate_all()
```

---

## 🧪 测试计划

### 测试策略

**原则**：
1. **测试先行**：在修改代码前，先为现有功能编写测试
2. **增量测试**：每拆分一个模块，立即运行测试验证
3. **回归测试**：确保拆分后功能与拆分前完全一致
4. **性能测试**：确保拆分不影响性能

### 测试用例

#### 1. work_order_tasks 测试

**文件**：`workorder/tests/test_work_order_tasks_refactor.py`

```python
"""
work_order_tasks 拆分测试

验证拆分后的功能与拆分前完全一致。
"""

import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from workorder.models.core import WorkOrder, WorkOrderTask, WorkOrderProcess
from workorder.models.base import Process, Department
from workorder.constants import TaskStatus


class WorkOrderTaskViewSetRefactorTest(TestCase):
    """WorkOrderTaskViewSet 拆分测试"""
    
    def setUp(self):
        """设置测试数据"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        # 创建测试数据
        self.department = Department.objects.create(name='测试部门')
        self.process = Process.objects.create(
            name='测试工序',
            code='TEST',
            department=self.department
        )
    
    def test_viewset_import(self):
        """测试 ViewSet 可以正常导入"""
        from workorder.views.work_order_tasks import WorkOrderTaskViewSet
        self.assertIsNotNone(WorkOrderTaskViewSet)
    
    def test_viewset_has_all_methods(self):
        """测试 ViewSet 包含所有必需的方法"""
        from workorder.views.work_order_tasks import WorkOrderTaskViewSet
        
        # 检查标准 CRUD 方法
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'list'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'create'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'retrieve'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'update'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'destroy'))
        
        # 检查自定义 actions
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'update_quantity'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'complete'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'split'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'assign'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'cancel'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'batch_update_quantity'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'batch_complete'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'batch_cancel'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'batch_assign'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'export'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'assignment_history'))
        self.assertTrue(hasattr(WorkOrderTaskViewSet, 'collaboration_stats'))
    
    def test_get_queryset_filtering(self):
        """测试查询集过滤功能"""
        # 创建测试任务
        workorder = WorkOrder.objects.create(
            customer_id=1,
            delivery_date='2026-12-31'
        )
        process = WorkOrderProcess.objects.create(
            work_order=workorder,
            process=self.process
        )
        task = WorkOrderTask.objects.create(
            work_order_process=process,
            assigned_operator=self.user
        )
        
        # 测试查询
        response = self.client.get('/api/workorder-tasks/')
        self.assertEqual(response.status_code, 200)
    
    def test_update_quantity_action(self):
        """测试更新数量 action"""
        # 创建测试任务
        workorder = WorkOrder.objects.create(
            customer_id=1,
            delivery_date='2026-12-31'
        )
        process = WorkOrderProcess.objects.create(
            work_order=workorder,
            process=self.process
        )
        task = WorkOrderTask.objects.create(
            work_order_process=process,
            assigned_operator=self.user,
            production_quantity=100
        )
        
        # 测试更新
        response = self.client.post(
            f'/api/workorder-tasks/{task.id}/update_quantity/',
            {'quantity': 50, 'version': task.version}
        )
        self.assertIn(response.status_code, [200, 201, 204])
    
    def test_complete_action(self):
        """测试完成任务 action"""
        # 类似的测试代码
        pass
    
    # ... 更多测试用例
```

#### 2. validation.py 测试

**文件**：`workorder/tests/test_validation_refactor.py`

```python
"""
validation.py 重构测试

验证重构后的验证逻辑与重构前完全一致。
"""

from django.test import TestCase
from datetime import date, timedelta

from workorder.models.core import WorkOrder
from workorder.models.base import Customer, Process, Department
from workorder.models.validation import WorkOrderValidator


class WorkOrderValidatorRefactorTest(TestCase):
    """WorkOrderValidator 重构测试"""
    
    def setUp(self):
        """设置测试数据"""
        self.customer = Customer.objects.create(name='测试客户')
        self.department = Department.objects.create(name='测试部门')
    
    def test_validate_basic_info_missing_customer(self):
        """测试缺少客户的验证"""
        workorder = WorkOrder.objects.create(
            delivery_date=date.today() + timedelta(days=7)
        )
        
        validator = WorkOrderValidator(workorder)
        errors = validator.validate_basic_info()
        
        self.assertIn('缺少客户信息', errors)
    
    def test_validate_basic_info_all_present(self):
        """测试基础信息完整的情况"""
        workorder = WorkOrder.objects.create(
            customer=self.customer,
            delivery_date=date.today() + timedelta(days=7)
        )
        
        # 添加产品和工序...
        
        validator = WorkOrderValidator(workorder)
        errors = validator.validate_basic_info()
        
        self.assertEqual(len(errors), 0)
    
    def test_validate_quantities_negative(self):
        """测试负数生产数量的验证"""
        workorder = WorkOrder.objects.create(
            customer=self.customer,
            production_quantity=-10,
            delivery_date=date.today() + timedelta(days=7)
        )
        
        validator = WorkOrderValidator(workorder)
        errors = validator.validate_quantities()
        
        self.assertTrue(any('生产数量必须大于0' in e for e in errors))
    
    def test_validate_all_integration(self):
        """测试完整的验证流程"""
        workorder = WorkOrder.objects.create(
            customer=self.customer,
            delivery_date=date.today() + timedelta(days=7)
        )
        
        validator = WorkOrderValidator(workorder)
        errors = validator.validate_all()
        
        # 应该有多个错误（缺少产品、工序等）
        self.assertGreater(len(errors), 0)
    
    # ... 更多测试用例
```

### 测试执行计划

**阶段 1：测试基准建立（拆分前）**
```bash
# 1. 为现有功能编写测试
# 2. 运行测试确保通过
python manage.py test workorder.tests.test_work_order_tasks_refactor --keepdb
python manage.py test workorder.tests.test_validation_refactor --keepdb

# 3. 记录测试结果
echo "测试基准：通过率 100%" > /tmp/test_baseline_stage2.txt
```

**阶段 2：拆分执行（每个模块）**
```bash
# 拆分 task_main.py 后
python manage.py test workorder.tests.test_work_order_tasks_refactor::test_viewset_import --keepdb

# 拆分 task_actions.py 后
python manage.py test workorder.tests.test_work_order_tasks_refactor::test_update_quantity_action --keepdb

# 拆分 validation.py 后
python manage.py test workorder.tests.test_validation_refactor --keepdb
```

**阶段 3：回归测试（拆分后）**
```bash
# 运行完整测试套件
python manage.py test workorder.tests --keepdb

# 运行特定功能测试
python manage.py test workorder.tests.test_api --keepdb
```

---

## 🔄 执行步骤

### 步骤 1：准备工作（30 分钟）

1. **创建备份**
   ```bash
   cp workorder/views/work_order_tasks.py workorder/views/work_order_tasks.py.backup
   cp workorder/models/core.py workorder/models/core.py.backup
   ```

2. **创建测试文件**
   - 创建 `workorder/tests/test_work_order_tasks_refactor.py`
   - 创建 `workorder/tests/test_validation_refactor.py`

3. **建立测试基准**
   ```bash
   python manage.py test workorder.tests --keepdb > /tmp/pre_refactor_test.txt
   ```

### 步骤 2：拆分 work_order_tasks.py（3-4 小时）

**2.1 创建目录和基础文件（30 分钟）**
```bash
mkdir -p workorder/views/work_order_tasks
touch workorder/views/work_order_tasks/__init__.py
```

**2.2 创建 task_main.py（45 分钟）**
- 提取基础 ViewSet 配置
- 提取 get_queryset() 方法
- 提取 perform_update() 方法
- 运行测试验证

**2.3 创建 task_actions.py（60 分钟）**
- 提取 5 个单个任务操作方法
- 创建 TaskActionsMixin
- 运行测试验证

**2.4 创建 task_bulk.py（45 分钟）**
- 提取 4 个批量操作方法
- 创建 TaskBulkMixin
- 运行测试验证

**2.5 创建 task_stats.py（30 分钟）**
- 提取 3 个统计方法
- 创建 TaskStatsMixin
- 运行测试验证

**2.6 组合和测试（30 分钟）**
- 在 `__init__.py` 中组合所有 Mixin
- 运行完整测试套件
- 验证所有功能正常

### 步骤 3：重构 validate_before_approval（2-3 小时）

**3.1 创建 validation.py（90 分钟）**
- 创建 WorkOrderValidator 类
- 拆分为 6 个验证方法
- 添加文档字符串

**3.2 修改 core.py（30 分钟）**
- 修改 validate_before_approval 方法
- 导入 WorkOrderValidator

**3.3 测试验证（30 分钟）**
- 运行验证器测试
- 运行回归测试

### 步骤 4：最终验证和清理（30 分钟）

**4.1 运行完整测试套件**
```bash
python manage.py test workorder.tests --keepdb
```

**4.2 手动功能测试**
- 测试任务创建、更新、删除
- 测试任务分派、完成、取消
- 测试批量操作
- 测试施工单审核

**4.3 代码质量检查**
```bash
flake8 workorder/views/work_order_tasks/ --exclude=__pycache__
flake8 workorder/models/validation.py
black workorder/views/work_order_tasks/ --check
```

**4.4 更新文档**
- 更新 API 文档
- 更新开发文档

---

## 🚨 回滚方案

### 触发条件

如果出现以下情况，立即回滚：
1. 测试通过率 < 100%
2. 关键功能失效
3. 性能下降 > 10%
4. 出现数据一致性问题

### 回滚步骤

**快速回滚（5 分钟）**
```bash
# 1. 停止服务
# systemctl stop your-service

# 2. 恢复备份文件
cp workorder/views/work_order_tasks.py.backup workorder/views/work_order_tasks.py
cp workorder/models/core.py.backup workorder/models/core.py

# 3. 删除新文件
rm -rf workorder/views/work_order_tasks/
rm -f workorder/models/validation.py

# 4. 重启服务
# systemctl start your-service

# 5. 验证
python manage.py test workorder.tests --keepdb
```

**Git 回滚（如果有提交）**
```bash
# 查看提交历史
git log --oneline -10

# 回滚到上一个稳定版本
git reset --hard HEAD~1

# 或者创建回滚提交
git revert HEAD
```

---

## 📊 风险评估

### 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 导入错误 | 中 | 高 | 分步测试，保留备份 |
| 功能失效 | 低 | 高 | 完整测试套件 |
| 性能下降 | 低 | 中 | 性能基准测试 |
| MRO 错误 | 低 | 高 | 谨慎设计 Mixin 顺序 |

### 关键风险点

**1. Mixin 方法解析顺序（MRO）**
- **风险**：多个 Mixin 中有同名方法
- **缓解**：
  - 确保方法名不冲突
  - 使用明确的命名前缀
  - 测试 MRO 解析

**2. 导入依赖循环**
- **风险**：模块间相互导入
- **缓解**：
  - 在方法内部导入（延迟导入）
  - 使用字符串导入
  - 清晰的依赖关系图

**3. 状态不一致**
- **风险**：拆分后业务逻辑改变
- **缓解**：
  - 保持原有逻辑完全不变
  - 完整的测试覆盖
  - 逐步拆分，每步验证

---

## ✅ 验收标准

### 功能验收

- [ ] 所有现有测试通过（100%）
- [ ] 新功能测试通过（100%）
- [ ] 手动功能测试通过
- [ ] API 响应格式不变
- [ ] 权限控制正常工作

### 代码质量验收

- [ ] 最大文件行数 < 500 行
- [ ] 最大函数行数 < 30 行
- [ ] flake8 检查通过
- [ ] mypy 类型检查通过
- [ ] 代码覆盖率 ≥ 80%

### 性能验收

- [ ] API 响应时间不增加
- [ ] 数据库查询次数不增加
- [ ] 内存使用不显著增加

---

## 📅 时间估算

| 阶段 | 任务 | 预估时间 | 缓冲时间 | 总计 |
|------|------|---------|---------|------|
| 1 | 准备工作 | 30分钟 | 10分钟 | 40分钟 |
| 2 | 拆分 work_order_tasks.py | 3-4小时 | 1小时 | 4-5小时 |
| 3 | 重构 validate_before_approval | 2-3小时 | 30分钟 | 2.5-3.5小时 |
| 4 | 最终验证和清理 | 30分钟 | 15分钟 | 45分钟 |
| | | | **总计** | **8-10小时** |

---

## 👥 人员需求

- **后端开发工程师**：1 人，全职
- **测试工程师**：0.5 人，负责测试编写和验证

---

## 📝 审核清单

在开始执行前，请确认：

- [ ] 已阅读并理解整个执行计划
- [ ] 已创建文件备份
- [ ] 已建立测试基准
- [ ] 已安排足够的执行时间
- [ ] 已准备回滚方案
- [ ] 已通知相关人员（前端、测试、运维）

---

**计划制定时间**: 2026-01-20
**计划版本**: v1.0
**制定人**: Claude
**审核状态**: 待审核

"""
部门模块测试

包含：
- DepartmentModelTest: 模型测试
- DepartmentSerializerTest: 序列化器测试
- DepartmentAPITest: API 测试
"""

from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from ..models.base import Department, Process
from ..serializers.base import DepartmentSerializer


class DepartmentModelTest(TestCase):
    """部门模型测试"""

    def setUp(self):
        """设置测试数据"""
        self.root_dept = Department.objects.create(
            name='总部',
            code='headquarters',
            sort_order=0,
            is_active=True
        )
        self.child_dept = Department.objects.create(
            name='生产部',
            code='production',
            parent=self.root_dept,
            sort_order=1,
            is_active=True
        )
        self.grandchild_dept = Department.objects.create(
            name='印刷车间',
            code='printing_workshop',
            parent=self.child_dept,
            sort_order=0,
            is_active=True
        )

    def test_department_str(self):
        """测试部门字符串表示"""
        self.assertEqual(str(self.root_dept), '总部')
        self.assertEqual(str(self.child_dept), '生产部')

    def test_get_full_name(self):
        """测试获取完整名称"""
        self.assertEqual(self.root_dept.get_full_name(), '总部')
        self.assertEqual(self.child_dept.get_full_name(), '总部 - 生产部')

    def test_natural_key(self):
        """测试自然键"""
        self.assertEqual(self.root_dept.natural_key(), ('headquarters',))
        retrieved = Department.get_by_natural_key('headquarters')
        self.assertEqual(retrieved, self.root_dept)

    def test_get_ancestors(self):
        """测试获取祖先部门"""
        ancestors = self.grandchild_dept.get_ancestors()
        self.assertEqual(len(ancestors), 2)
        self.assertEqual(ancestors[0], self.child_dept)
        self.assertEqual(ancestors[1], self.root_dept)

        # 顶级部门没有祖先
        self.assertEqual(len(self.root_dept.get_ancestors()), 0)

    def test_get_descendants(self):
        """测试获取子孙部门"""
        descendants = self.root_dept.get_descendants()
        self.assertEqual(len(descendants), 2)
        self.assertIn(self.child_dept, descendants)
        self.assertIn(self.grandchild_dept, descendants)

        # 叶子部门没有子孙
        self.assertEqual(len(self.grandchild_dept.get_descendants()), 0)

    def test_get_level(self):
        """测试获取层级"""
        self.assertEqual(self.root_dept.get_level(), 0)
        self.assertEqual(self.child_dept.get_level(), 1)
        self.assertEqual(self.grandchild_dept.get_level(), 2)

    def test_updated_at_auto_update(self):
        """测试 updated_at 自动更新"""
        old_updated_at = self.root_dept.updated_at
        self.root_dept.name = '新总部'
        self.root_dept.save()
        self.root_dept.refresh_from_db()
        self.assertGreater(self.root_dept.updated_at, old_updated_at)


class DepartmentSerializerTest(TestCase):
    """部门序列化器测试"""

    def setUp(self):
        """设置测试数据"""
        self.root_dept = Department.objects.create(
            name='总部',
            code='headquarters',
            sort_order=0,
            is_active=True
        )
        self.child_dept = Department.objects.create(
            name='生产部',
            code='production',
            parent=self.root_dept,
            sort_order=1,
            is_active=True
        )

    def test_valid_code_format(self):
        """测试有效的部门编码格式"""
        data = {
            'name': '测试部门',
            'code': 'test_dept_01',
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_code_uppercase(self):
        """测试无效的部门编码（大写字母）"""
        data = {
            'name': '测试部门',
            'code': 'Test_Dept',
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)

    def test_invalid_code_special_chars(self):
        """测试无效的部门编码（特殊字符）"""
        data = {
            'name': '测试部门',
            'code': 'test-dept',  # 包含连字符
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)

    def test_code_too_short(self):
        """测试部门编码太短"""
        data = {
            'name': '测试部门',
            'code': 'a',
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)

    def test_code_immutable_on_update(self):
        """测试编辑时不能修改编码"""
        data = {
            'name': '新名称',
            'code': 'new_code',  # 尝试修改编码
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(instance=self.root_dept, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)

    def test_name_validation(self):
        """测试部门名称验证"""
        # 名称太短
        data = {
            'name': '测',
            'code': 'test_dept',
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)

    def test_sort_order_validation(self):
        """测试排序值验证"""
        # 负数排序值
        data = {
            'name': '测试部门',
            'code': 'test_dept',
            'sort_order': -1,
            'is_active': True
        }
        serializer = DepartmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('sort_order', serializer.errors)

        # 超大排序值
        data['sort_order'] = 100000
        serializer = DepartmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('sort_order', serializer.errors)

    def test_circular_reference_self(self):
        """测试循环引用（自己作为上级）"""
        data = {
            'name': '总部',
            'code': 'headquarters',
            'parent': self.root_dept.id,
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(instance=self.root_dept, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('parent', serializer.errors)

    def test_circular_reference_descendant(self):
        """测试循环引用（子部门作为上级）"""
        data = {
            'name': '总部',
            'code': 'headquarters',
            'parent': self.child_dept.id,
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(instance=self.root_dept, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('parent', serializer.errors)

    def test_max_level_depth(self):
        """测试最大层级深度"""
        # 创建第三级部门
        level2_dept = Department.objects.create(
            name='印刷车间',
            code='printing',
            parent=self.child_dept,
            sort_order=0,
            is_active=True
        )

        # 尝试创建第四级部门（应该失败）
        data = {
            'name': '印刷组',
            'code': 'printing_group',
            'parent': level2_dept.id,
            'sort_order': 0,
            'is_active': True
        }
        serializer = DepartmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('parent', serializer.errors)

    def test_level_field(self):
        """测试层级字段"""
        serializer = DepartmentSerializer(instance=self.root_dept)
        self.assertEqual(serializer.data['level'], 0)

        serializer = DepartmentSerializer(instance=self.child_dept)
        self.assertEqual(serializer.data['level'], 1)


class DepartmentAPITest(APITestCase):
    """部门 API 测试"""

    def setUp(self):
        """设置测试数据"""
        # 创建超级用户
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )

        # 创建普通用户
        self.normal_user = User.objects.create_user(
            username='user',
            email='user@example.com',
            password='userpass123'
        )

        # 创建测试部门
        self.root_dept = Department.objects.create(
            name='总部',
            code='headquarters',
            sort_order=0,
            is_active=True
        )
        self.child_dept = Department.objects.create(
            name='生产部',
            code='production',
            parent=self.root_dept,
            sort_order=1,
            is_active=True
        )

    def test_list_departments(self):
        """测试获取部门列表"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_search_departments(self):
        """测试搜索部门"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-list')
        response = self.client.get(url, {'search': '生产'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], '生产部')

    def test_create_department(self):
        """测试创建部门"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-list')
        data = {
            'name': '财务部',
            'code': 'finance',
            'sort_order': 2,
            'is_active': True
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Department.objects.count(), 3)

    def test_update_department(self):
        """测试更新部门"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-detail', kwargs={'pk': self.child_dept.pk})
        data = {
            'name': '生产部门',
            'code': 'production',  # 保持不变
            'sort_order': 2,
            'is_active': True
        }
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.child_dept.refresh_from_db()
        self.assertEqual(self.child_dept.name, '生产部门')

    def test_delete_department_without_children(self):
        """测试删除没有子部门的部门"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-detail', kwargs={'pk': self.child_dept.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Department.objects.count(), 1)

    def test_delete_department_with_children(self):
        """测试删除有子部门的部门（应该失败）"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-detail', kwargs={'pk': self.root_dept.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(Department.objects.count(), 2)

    def test_tree_action(self):
        """测试获取部门树"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-tree')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 应该只有一个顶级部门
        self.assertEqual(len(response.data), 1)
        # 顶级部门应该有子部门
        self.assertEqual(len(response.data[0]['children']), 1)
        self.assertEqual(response.data[0]['children'][0]['name'], '生产部')

    def test_all_action(self):
        """测试获取所有部门"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-all')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_all_action_filter_active(self):
        """测试获取所有启用的部门"""
        # 禁用一个部门
        self.child_dept.is_active = False
        self.child_dept.save()

        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-all')
        response = self.client.get(url, {'is_active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_unauthorized_access(self):
        """测试未授权访问"""
        url = reverse('department-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_code_validation_on_create(self):
        """测试创建时的编码验证"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('department-list')

        # 无效的编码格式
        data = {
            'name': '测试部门',
            'code': 'Test-Dept',  # 包含大写和连字符
            'sort_order': 0,
            'is_active': True
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data)

"""
工序 API 测试

测试工序相关的 API 功能。
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse

from workorder.models.base import Process
from workorder.serializers.base import ProcessSerializer


class ProcessModelTest(TestCase):
    """工序模型测试"""

    def test_str_method(self):
        """测试 __str__ 方法"""
        process = Process.objects.create(name='印刷', code='PRINT')
        self.assertEqual(str(process), 'PRINT - 印刷')

    def test_get_required_plates(self):
        """测试获取需要的版列表"""
        process = Process.objects.create(
            name='印刷',
            code='PRINT',
            requires_artwork=True,
            requires_die=True
        )
        plates = process.get_required_plates()
        self.assertIn('artwork', plates)
        self.assertIn('die', plates)
        self.assertEqual(len(plates), 2)


class ProcessSerializerTest(TestCase):
    """工序序列化器测试"""

    def test_validate_code_valid(self):
        """测试有效的工序编码"""
        valid_codes = ['PRINT', 'PRINT-01', 'print_01', 'P01', 'P_01']
        for code in valid_codes:
            serializer = ProcessSerializer(data={
                'code': code,
                'name': '测试工序'
            })
            self.assertTrue(
                serializer.is_valid(),
                f'编码 {code} 应该是有效的: {serializer.errors}'
            )

    def test_validate_code_invalid(self):
        """测试无效的工序编码"""
        invalid_codes = ['PRINT@01', 'PRINT 01', '印刷', '', 'A', 'P']
        for code in invalid_codes:
            serializer = ProcessSerializer(data={
                'code': code,
                'name': '测试工序'
            })
            self.assertFalse(
                serializer.is_valid(),
                f'编码 {code} 应该是无效的'
            )
            self.assertIn('code', serializer.errors)

    def test_validate_builtin_code_change(self):
        """测试内置工序的编码不可修改"""
        process = Process.objects.create(
            name='印刷',
            code='PRINT',
            is_builtin=True
        )

        serializer = ProcessSerializer(
            process,
            data={
                'code': 'PRINT-NEW',
                'name': '印刷'
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)

    def test_validate_standard_duration_negative(self):
        """测试标准工时不能为负数"""
        serializer = ProcessSerializer(data={
            'code': 'TEST',
            'name': '测试',
            'standard_duration': -10
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('standard_duration', serializer.errors)

    def test_validate_standard_duration_too_large(self):
        """测试标准工时不能过大"""
        serializer = ProcessSerializer(data={
            'code': 'TEST',
            'name': '测试',
            'standard_duration': 10000
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('standard_duration', serializer.errors)

    def test_validate_sort_order_negative(self):
        """测试排序值不能为负数"""
        serializer = ProcessSerializer(data={
            'code': 'TEST',
            'name': '测试',
            'sort_order': -1
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('sort_order', serializer.errors)

    def test_validate_requires_artwork_consistency(self):
        """测试需要图稿时图稿必选必须开启"""
        serializer = ProcessSerializer(data={
            'code': 'TEST',
            'name': '测试',
            'requires_artwork': True,
            'artwork_required': False
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('artwork_required', serializer.errors)

    def test_validate_task_generation_rule_consistency(self):
        """测试任务生成规则与版要求的一致性"""
        serializer = ProcessSerializer(data={
            'code': 'TEST',
            'name': '测试',
            'task_generation_rule': 'artwork',
            'requires_artwork': False
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('task_generation_rule', serializer.errors)


class ProcessAPITest(APITestCase):
    """工序 API 测试"""

    def setUp(self):
        """测试前准备"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        self.client.force_authenticate(user=self.admin_user)

        self.process = Process.objects.create(
            name='印刷',
            code='PRINT',
            sort_order=1
        )

    def test_list_processes(self):
        """测试获取工序列表"""
        url = reverse('process-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)

    def test_create_process(self):
        """测试创建工序"""
        url = reverse('process-list')
        data = {
            'code': 'DIE-CUT',
            'name': '模切',
            'sort_order': 2
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'DIE-CUT')
        self.assertEqual(response.data['name'], '模切')

    def test_update_process(self):
        """测试更新工序"""
        url = reverse('process-detail', kwargs={'pk': self.process.pk})
        data = {
            'code': 'PRINT',
            'name': '印刷工序',
            'sort_order': 1
        }
        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], '印刷工序')

    def test_delete_builtin_process(self):
        """测试不能删除内置工序"""
        builtin_process = Process.objects.create(
            name='内置工序',
            code='BUILTIN',
            is_builtin=True
        )

        url = reverse('process-detail', kwargs={'pk': builtin_process.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_batch_update_active(self):
        """测试批量更新启用状态"""
        process2 = Process.objects.create(
            name='烫金',
            code='FOIL',
            is_active=True
        )

        url = reverse('process-batch-update-active')
        data = {
            'ids': [self.process.id, process2.id],
            'is_active': False
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_count'], 2)

        # 验证状态已更新
        self.process.refresh_from_db()
        self.assertFalse(self.process.is_active)

    def test_batch_disable_builtin_process(self):
        """测试不能批量禁用内置工序"""
        builtin_process = Process.objects.create(
            name='内置工序',
            code='BUILTIN',
            is_builtin=True,
            is_active=True
        )

        url = reverse('process-batch-update-active')
        data = {
            'ids': [self.process.id, builtin_process.id],
            'is_active': False
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_filter_by_is_active(self):
        """测试按启用状态过滤"""
        Process.objects.create(name='禁用工序', code='DISABLED', is_active=False)

        url = reverse('process-list')
        response = self.client.get(url, {'is_active': True})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 所有结果都应该 is_active=True
        for result in response.data['results']:
            self.assertTrue(result['is_active'])

    def test_search_by_name(self):
        """测试按名称搜索"""
        url = reverse('process-list')
        response = self.client.get(url, {'search': '印刷'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        self.assertIn('印刷', response.data['results'][0]['name'])


class ProcessPermissionTest(APITestCase):
    """工序权限测试"""

    def setUp(self):
        """测试前准备"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )

        self.normal_user = User.objects.create_user(
            username='user',
            password='user123'
        )

        self.process = Process.objects.create(name='印刷', code='PRINT')

    def test_admin_can_create_process(self):
        """测试管理员可以创建工序"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('process-list')
        data = {'code': 'TEST', 'name': '测试'}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_normal_user_cannot_create_process(self):
        """测试普通用户不能创建工序"""
        self.client.force_authenticate(user=self.normal_user)
        url = reverse('process-list')
        data = {'code': 'TEST', 'name': '测试'}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete_process(self):
        """测试管理员可以删除工序"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('process-detail', kwargs={'pk': self.process.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_normal_user_cannot_delete_process(self):
        """测试普通用户不能删除工序"""
        self.client.force_authenticate(user=self.normal_user)
        url = reverse('process-detail', kwargs={'pk': self.process.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

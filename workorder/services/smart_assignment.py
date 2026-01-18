"""
智能任务分派算法优化

实现基于以下策略的智能任务分派：
1. 技能画像和技能匹配
2. 工作负载均衡
3. 历史绩效考虑
4. 动态优先级调整
5. 学习型算法优化
"""

from django.db import models
from django.db.models import Count, Q, Avg, Max, Min
from django.utils import timezone
from typing import List, Dict, Optional, Tuple, Any
import logging
import numpy as np
from datetime import timedelta, datetime
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class SkillProfile(models.Model):
    """操作员技能画像"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='skill_profile')
    
    # 核心技能领域
    technical_skills = models.JSONField('技术技能', default=list, help_text='掌握的技术栈')
    experience_years = models.IntegerField('经验年限', default=0)
    skill_level = models.IntegerField('技能等级', default=1, help_text='1-10级')
    certification = models.JSONField('认证证书', default=list)
    
    # 性能指标
    task_completion_rate = models.FloatField('任务完成率', default=0.0, help_text='最近30天任务完成率')
    avg_completion_time = models.FloatField('平均完成时间(小时)', default=0.0, help_text='平均任务完成时间')
    error_rate = models.FloatField('错误率', default=0.0, help_text='错误率')
    quality_score = models.FloatField('质量评分', default=0.0, help_text='质量评分(0-10)')
    
    # 工作偏好
    preferred_work_types = models.JSONField('偏好的工作类型', default=list)
    work_capacity = models.IntegerField('工作容量', default=5, help_text='同时处理的最大任务数')
    
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '技能画像'
        verbose_name_plural = '技能画像管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['skill_level']),
        ]


class TaskPerformanceData:
    """任务性能数据"""
    
    def __init__(self):
        self.completion_times = []
        self.error_counts = defaultdict(int)
        self.quality_scores = []
        self.task_counts = defaultdict(int)
    
    def add_completion_time(self, duration_hours: float, quality_score: float):
        self.completion_times.append(duration_hours)
        
    def add_error(self, error_type: str):
        self.error_counts[error_type] += 1
    
    def add_quality_score(self, quality_score: float):
        self.quality_scores.append(quality_score)
    
    def add_task_count(self):
        self.task_counts['total'] += 1
    
    def get_avg_completion_time(self) -> float:
        return np.mean(self.completion_times) if self.completion_times else 0
    
    def get_error_rate(self) -> float:
        total_tasks = sum(self.task_counts.values())
        total_errors = sum(self.error_counts.values())
        return total_errors / total_tasks if total_tasks > 0 else 0
    
    def get_quality_score(self) -> float:
        return np.mean(self.quality_scores) if self.quality_scores else 0
    
    def get_performance_score(self) -> float:
        # 综合多个指标计算性能评分
        completion_rate = self.get_completion_rate()
        error_rate = self.get_error_rate()
        quality_score = self.get_quality_score()
        avg_completion_time = self.get_avg_completion_time()
        
        # 权重指标
        weights = {
            'completion_rate': 0.4,    # 完成率最重要
            'error_rate': 0.3,    # 错误率第二重要
            'quality_score': 0.2,    # 质量评分第三重要
            'avg_completion_time': 0.1,    # 平均时间也要考虑
        }
        
        score = (
            weights['completion_rate'] * completion_rate +
            weights['error_rate'] * (1 - error_rate) +
            weights['quality_score'] * quality_score +
            weights['avg_completion_time'] * (1 / max(avg_completion_time, 1))
        )
        
        return min(max(score, 0.1))


class SmartAssignmentService:
    """智能任务分派服务"""
    
    @staticmethod
    def get_skill_profile(user) -> Optional[SkillProfile]:
        """获取用户技能画像"""
        try:
            return user.skill_profile
        except SkillProfile.DoesNotExist:
            return None
    
    @staticmethod
    def calculate_skill_match_score(user_skills: List[str], task_requirements: List[str]) -> float:
        """计算技能匹配度"""
        required_skills = set(skill.lower() for skill in task_requirements if skill)
        user_skills = set(skill.lower() for skill in user_skills if skill)
        
        if not required_skills:
            return 0.0
        
        # 计算匹配度
        matched_skills = required_skills & user_skills
        match_count = len(matched_skills)
        total_count = len(required_skills)
        
        if total_count == 0:
            return 0.0
        
        # 基础匹配度
        base_score = match_count / total_count
        weight = 0.6  # 基础匹配权重
        
        # 技能等级权重
        skill_level_weights = {
            1: 0.3,
            2: 0.5,
            3: 0.7,
            4: 0.9,
            5: 1.0,
            6: 1.2,
            7: 1.5,
            8: 1.8,
            9: 2.0,
            10: 2.2,
        }
        
        total_score = 0.0
        for skill in matched_skills:
            level = 1
            while level <= 10 and skill_level_weights.get(level, 0) < 1.0:
                level += 1
            
            skill_level_weight = skill_level_weights.get(level, 1.0)
            total_score += skill_level_weight
        
        # 技能不匹配的惩罚
        penalty = (total_count - match_count) * 0.2)
        
        return min(base_score + total_score - penalty, 1.0)
    
    @staticmethod
    def calculate_workload_factor(user, current_tasks: int) -> float:
        """计算工作负载因子"""
        user_profile = SmartAssignmentService.get_skill_profile(user)
        if not user_profile:
            return 1.0  # 默认中等负载
        
        capacity = user_profile.work_capacity or 5
        current_load = current_tasks / capacity
        
        # 工作负载因子（1.0-3.0）
        if current_load <= 0.2:
            return 0.8
        elif current_load <= 0.5:
            return 0.6
        elif current_load <= 0.8:
            return 0.4
        elif current_load <= 1.0:
            return 1.2
        elif current_load <= 1.5:
            return 1.5
        elif current_load <= 2.0:
            return 1.8
        else:
            return 2.0
    
    @staticmethod
    def calculate_priority_score(user, task_priority: str, deadline_days: int = None) -> float:
        """计算优先级评分"""
        user_profile = SmartAssignmentService.get_skill_profile(user)
        if not user_profile:
            return 0.0
        
        # 基础优先级评分
        priority_scores = {
            'urgent': 1.0,
            'high': 0.8,
            'normal': 0.6,
            'low': 0.4,
        }
        
        base_score = priority_scores.get(task_priority, 0.6)
        
        # 交货日期紧急度
        if deadline_days:
            if deadline_days <= 1:
                urgency_factor = 1.5
            elif deadline_days <= 3:
                urgency_factor = 1.2
            elif deadline_days <= 7:
                urgency_factor = 1.0
            else:
                urgency_factor = 0.8
        
        # 技能匹配度加成
        skill_match = user_profile.skill_level or 1
        
        total_score = base_score + urgency_factor + (skill_match * 0.2)
        return min(total_score, 2.0)
    
    @staticmethod
    def get_optimal_operator(user, task_requirements: Dict[str, None]) -> Optional[User]:
        """获取最佳操作员选择"""
        user_profile = SmartAssignmentService.get_skill_profile(user)
        if not user_profile:
            return None
        
        # 获取符合要求的候选人
        available_users = User.objects.filter(
            is_active=True,
            skill_profile__technical_skills__contains=any(skill.lower() for skill in task_requirements if skill)
        )
        
        if not available_users.exists():
            return None
        
        # 计算每个候选人的适配度分数
        candidates_scores = []
        for user in available_users:
            score = SmartAssignmentService.calculate_user_match_score(user, task_requirements)
            candidates_scores.append(score)
        
        # 选择得分最高的用户
        if candidates_scores:
            return max(range(len(candidates_scores)), key=lambda i: candidates_scores[i])
        return None

    @staticmethod
    def calculate_user_match_score(user, task_requirements: Dict[str, None]) -> float:
        """计算用户匹配度"""
        user_profile = SmartAssignmentService.get_skill_profile(user)
        if not user_profile:
            return 0.0
        
        score = SmartAssignmentService.calculate_skill_match_score(
            user_profile.technical_skills or [],
            task_requirements or []
        )
        
        # 考虑工作负载
        current_tasks = TaskPerformanceData.get_user_task_count(user)
        workload_factor = SmartAssignmentService.calculate_workload_factor(user, current_tasks)
        workload_score = min(workload_factor, 2.0)
        
        return min(score + workload_score, 2.0)

    @staticmethod
    def calculate_team_balance_score(team_users: List[User]) -> Dict[str, float]:
        """计算团队平衡性评分"""
        skill_levels = [user.skill_profile.skill_level for user in team_users if user.skill_profile else 0]
        work_capacities = [user.work_capacity for user in team_users if user.skill_profile else 5]
        
        # 团队技能多样性
        skill_diversity = len(set(
            skill.lower() for user in team_users for skill in user_profile.technical_skills or [] for user in team_users if user.skill_profile
        ))
        
        # 平衡度计算
        avg_skill_level = np.mean(skill_levels) if skill_levels else [1.0])
        capacity_variance = np.var(work_capacities) if work_capacities else [1.0])
        
        # 平衡度评分：技能多样性 + 容量平衡
        diversity_score = (skill_diversity / len(skill_levels)) * 0.4
        balance_score = (1 / capacity_variance) * 0.6
        team_score = diversity_score + balance_score
        
        return {
            'avg_skill_level': avg_skill_level,
            'diversity_score': diversity_score,
            'balance_score': balance_score,
            'team_score': team_score
        }


class LearningSystem:
    """学习系统，用于优化分派算法"""
    
    def __init__(self):
        self.performance_data = TaskPerformanceData()
        self.user_performance = {}  # 用户ID -> 性能数据
        self.skill_success_rates = {}  # 用户ID -> 技能成功率
    
    def record_performance(self, user_id: int, task_id: str, success: bool, 
                    completion_time: float = None, quality_score: float = None):
        """记录任务性能数据"""
        if user_id not in self.user_performance:
            self.user_performance[user_id] = TaskPerformanceData()
        
        performance_data = self.user_performance[user_id]
        
        if success and completion_time:
            performance_data.add_completion_time(completion_time)
        if quality_score:
            performance_data.add_quality_score(quality_score)
        performance_data.add_task_count()
        performance_data.add_error_count(not success)
        performance_data.add_success()
        
        performance_data.update_avg_completion_time()
        performance_data.update_error_rate()
        performance_data.update_quality_score()
        
        logger.info(f"记录用户 {user_id} 的任务 {task_id} 性能数据: "
                   f"成功={success}, "
                   f"耗时={completion_time}h, "
                   f"质量评分={quality_score}")

    def get_user_performance_summary(self, user_id: int) -> Dict[str, Any]:
        """获取用户性能汇总"""
        performance_data = self.user_performance.get(user_id)
        
        if not performance_data:
            return {
                'total_tasks': 0,
                'success_rate': 0,
                'avg_completion_time': 0,
                'error_rate': 0,
                'quality_score': 0
            }
        
        return {
            'total_tasks': performance_data.task_count,
            'success_rate': performance_data.get_success_rate(),
            'avg_completion_time': performance_data.get_avg_completion_time(),
            'error_rate': performance_data.get_error_rate(),
            'quality_score': performance_data.get_quality_score(),
            'skill_level': performance_data.get_skill_level(),
        }

    def update_skill_success_rate(self, user_id: int, skill_type: str, success_rate: float):
        """更新技能成功率"""
        if user_id not in self.user_performance:
            self.user_performance[user_id] = TaskPerformanceData()
        
        if skill_type in self.user_performance[user_id].skill_success_rates:
            self.user_performance[user_id].skill_success_rates[skill_type] = success_rate
        
        self.user_performance[user_id].update_avg_completion_time()
        self.user_performance[user_id].update_error_rate()
        self.user_performance[user_id].update_quality_score()
        logger.info(f"用户 {user_id} 的 {skill_type} 技能成功率更新为 {success_rate}")

    def update_skill_level(self, user_id: int, new_level: int):
        """更新用户技能等级"""
        if user_id not in self.user_performance:
            self.user_performance[user_id] = SkillProfile.objects.get(user=user_id)
            self.user_performance[user_id].skill_level = new_level
            self.user_performance[user_id].save()

    def get_system_recommendations(self) -> Dict[str, Any]:
        """获取系统改进建议"""
        
        # 分析整体性能数据
        all_users = User.objects.filter(
            is_active=True,
            skill_profile__isnull=False
        ).select_related('skill_profile')
        
        if not all_users.exists():
            return {}
        
        total_performance = TaskPerformanceData()
        for user in all_users:
            perf_summary = self.get_user_performance_summary(user.id)
            if perf_summary:
                total_performance.task_count += perf_summary['total_tasks']
                total_performance.success_rate += perf_summary['success_rate']
                total_performance.avg_completion_time += perf_summary['avg_completion_time']
                total_performance.error_rate += perf_summary['error_rate']
                total_performance.quality_score += perf_summary['quality_score']
                total_performance.skill_level = perf_summary['skill_level']
        
        # 分析问题和改进建议
        recommendations = []
        
        # 检查技能不匹配的用户
        skill_mismatch_users = []
        for user in all_users:
            user_profile = user.skill_profile
            recent_performance = self.get_user_performance_summary(user.id)
            
            # 检查技能匹配度
            skill_match_score = user_profile.skill_level / 10.0
            if skill_match_score < 0.3:
                skill_mismatch_users.append(user)
        
        # 检查工作负载不均衡
        workload_scores = []
        for user in all_users:
            workload_score = SmartAssignmentService.calculate_workload_factor(user, TaskPerformanceData.get_user_task_count(user))
            if workload_score > 1.5:  # 负载过高
                workload_scores.append(user)
        
        if skill_mismatch_users:
            recommendations.append({
                'type': 'skill_mismatch',
                'message': f'用户 {user.username} 的技能与任务需求不匹配',
                'suggestion': '建议参加相关技能培训'
            })
        
        if workload_scores:
            recommendations.append({
                'type': 'workload_imbalance',
                'message': '团队工作量分配不均衡，建议重新分配任务',
                'affected_users': [u.username for u in workload_scores]
            })
        
        return {
            'total_users': all_users.count(),
            'performance_summary': total_performance.get_performance_summary(),
            'recommendations': recommendations
        }
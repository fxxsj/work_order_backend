from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
import re


class CustomUserCreationForm(UserCreationForm):
    """自定义用户创建表单，允许中文用户名"""
    
    class Meta:
        model = User
        fields = ("username",)
        field_classes = {}
    
    def clean_username(self):
        """自定义用户名验证，允许中文"""
        username = self.cleaned_data.get("username")
        
        # 允许中文、字母、数字、下划线、连字符
        if not re.match(r'^[\w\u4e00-\u9fa5-]+$', username):
            raise forms.ValidationError(
                '用户名只能包含字母、数字、下划线、连字符和中文字符。'
            )
        
        # 检查用户名是否已存在
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('该用户名已被使用。')
        
        return username


class CustomUserChangeForm(UserChangeForm):
    """自定义用户修改表单，允许中文用户名"""
    
    class Meta:
        model = User
        fields = '__all__'
        field_classes = {}
    
    def clean_username(self):
        """自定义用户名验证，允许中文"""
        username = self.cleaned_data.get("username")
        
        # 允许中文、字母、数字、下划线、连字符
        if not re.match(r'^[\w\u4e00-\u9fa5-]+$', username):
            raise forms.ValidationError(
                '用户名只能包含字母、数字、下划线、连字符和中文字符。'
            )
        
        return username


class CustomUserAdmin(BaseUserAdmin):
    """自定义用户管理，使用支持中文的表单"""
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    # 复制默认的 fieldsets 和 add_fieldsets
    fieldsets = BaseUserAdmin.fieldsets
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
    )


# 重新注册 User 模型
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


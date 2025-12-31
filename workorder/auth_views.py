from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.views.decorators.csrf import ensure_csrf_cookie
from .serializers import UserSerializer
import re


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """用户登录"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': '请提供用户名和密码'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        login(request, user)
        # 获取用户所属的组
        groups = list(user.groups.values_list('name', flat=True))
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'groups': groups,
            'is_salesperson': '业务员' in groups,
        })
    else:
        return Response(
            {'error': '用户名或密码错误'},
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """用户登出"""
    logout(request)
    return Response({'message': '已成功登出'})


@api_view(['GET'])
@ensure_csrf_cookie
@permission_classes([AllowAny])
def get_current_user(request):
    """获取当前登录用户信息"""
    if request.user.is_authenticated:
        # 获取用户所属的组
        groups = list(request.user.groups.values_list('name', flat=True))
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
            'groups': groups,
            'is_salesperson': '业务员' in groups,
        })
    else:
        return Response(
            {'error': '未登录'},
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """用户注册"""
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email', '')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')
    
    if not username or not password:
        return Response(
            {'error': '请提供用户名和密码'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # 验证用户名格式（允许中文、字母、数字、下划线、连字符）
    if not re.match(r'^[\w\u4e00-\u9fa5-]+$', username):
        return Response(
            {'error': '用户名只能包含字母、数字、下划线、连字符和中文字符'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if User.objects.filter(username=username).exists():
        return Response(
            {'error': '用户名已存在'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name
    )
    
    # 自动登录
    login(request, user)
    
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_salespersons(request):
    """获取业务员列表"""
    try:
        # 获取"业务员"组
        salesperson_group = Group.objects.filter(name='业务员').first()
        
        if salesperson_group:
            # 获取属于业务员组的用户
            salespersons = salesperson_group.user_set.filter(is_active=True).order_by('username')
        else:
            # 如果业务员组不存在，返回空列表
            salespersons = User.objects.none()
        
        serializer = UserSerializer(salespersons, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


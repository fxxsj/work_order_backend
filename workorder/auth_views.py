from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group, Permission
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils.decorators import method_decorator
from .serializers import UserSerializer
from workorder.response import APIResponse
from workorder.schema import standard_error_response, standard_success_response
import re


class EmptySerializer(serializers.Serializer):
    """用于 OpenAPI 生成的空序列化器"""

    pass


login_request_serializer = inline_serializer(
    name="LoginRequest",
    fields={
        "username": serializers.CharField(),
        "password": serializers.CharField(),
    },
)

login_data_serializer = inline_serializer(
    name="LoginResponseData",
    fields={
        "id": serializers.IntegerField(),
        "username": serializers.CharField(),
        "email": serializers.CharField(required=False, allow_blank=True),
        "first_name": serializers.CharField(required=False, allow_blank=True),
        "last_name": serializers.CharField(required=False, allow_blank=True),
        "is_staff": serializers.BooleanField(),
        "is_superuser": serializers.BooleanField(),
        "groups": serializers.ListField(child=serializers.CharField()),
        "is_salesperson": serializers.BooleanField(),
        "permissions": serializers.ListField(child=serializers.CharField()),
        "access": serializers.CharField(),
        "refresh": serializers.CharField(),
    },
)

register_request_serializer = inline_serializer(
    name="RegisterRequest",
    fields={
        "username": serializers.CharField(),
        "password": serializers.CharField(),
        "email": serializers.CharField(required=False, allow_blank=True),
        "first_name": serializers.CharField(required=False, allow_blank=True),
        "last_name": serializers.CharField(required=False, allow_blank=True),
    },
)

register_data_serializer = inline_serializer(
    name="RegisterResponseData",
    fields={
        "id": serializers.IntegerField(),
        "username": serializers.CharField(),
        "email": serializers.CharField(required=False, allow_blank=True),
        "first_name": serializers.CharField(required=False, allow_blank=True),
        "last_name": serializers.CharField(required=False, allow_blank=True),
    },
)

current_user_data_serializer = inline_serializer(
    name="CurrentUserData",
    fields={
        "id": serializers.IntegerField(),
        "username": serializers.CharField(),
        "email": serializers.CharField(required=False, allow_blank=True),
        "first_name": serializers.CharField(required=False, allow_blank=True),
        "last_name": serializers.CharField(required=False, allow_blank=True),
        "is_staff": serializers.BooleanField(),
        "is_superuser": serializers.BooleanField(),
        "groups": serializers.ListField(child=serializers.CharField()),
        "is_salesperson": serializers.BooleanField(),
        "permissions": serializers.ListField(child=serializers.CharField()),
    },
)

change_password_request_serializer = inline_serializer(
    name="ChangePasswordRequest",
    fields={
        "old_password": serializers.CharField(),
        "new_password": serializers.CharField(),
        "confirm_password": serializers.CharField(),
    },
)

update_profile_request_serializer = inline_serializer(
    name="UpdateProfileRequest",
    fields={
        "email": serializers.CharField(required=False, allow_blank=True),
        "first_name": serializers.CharField(required=False, allow_blank=True),
        "last_name": serializers.CharField(required=False, allow_blank=True),
    },
)

update_profile_data_serializer = inline_serializer(
    name="UpdateProfileResponseData",
    fields={
        "id": serializers.IntegerField(),
        "username": serializers.CharField(),
        "email": serializers.CharField(required=False, allow_blank=True),
        "first_name": serializers.CharField(required=False, allow_blank=True),
        "last_name": serializers.CharField(required=False, allow_blank=True),
        "is_staff": serializers.BooleanField(),
        "is_superuser": serializers.BooleanField(),
        "groups": serializers.ListField(child=serializers.CharField()),
        "permissions": serializers.ListField(child=serializers.CharField()),
    },
)

token_refresh_request_serializer = inline_serializer(
    name="TokenRefreshRequest",
    fields={"refresh": serializers.CharField()},
)

token_refresh_response_serializer = inline_serializer(
    name="TokenRefreshResponse",
    fields={
        "access": serializers.CharField(),
        "refresh": serializers.CharField(required=False),
    },
)


class LoginView(APIView):
    """用户登录视图"""
    permission_classes = [AllowAny]
    authentication_classes = []  # 禁用所有认证类，避免 CSRF 检查

    @extend_schema(
        tags=["用户"],
        summary="用户登录",
        request=login_request_serializer,
        responses={
            200: OpenApiResponse(
                response=standard_success_response("LoginResponse", login_data_serializer),
                description="登录成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("LoginBadRequest"),
                description="请求无效",
            ),
            401: OpenApiResponse(
                response=standard_error_response("LoginUnauthorized"),
                description="用户名或密码错误",
            ),
        },
    )
    def post(self, request):
        """用户登录"""
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return APIResponse.error('请提供用户名和密码', code=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            refresh = RefreshToken.for_user(user)

            # 获取用户所属的组
            groups = list(user.groups.values_list('name', flat=True))

            # 获取用户权限（用于前端权限控制）
            permissions = []
            if user.is_superuser:
                permissions = ['*']
            else:
                permissions = list(user.get_all_permissions())

            return APIResponse.success(data={
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'groups': groups,
                'is_salesperson': '业务员' in groups,
                'permissions': permissions,  # 添加权限列表
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            })
        else:
            return APIResponse.error('用户名或密码错误', code=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """用户登出视图"""

    permission_classes = [IsAuthenticated]
    serializer_class = EmptySerializer

    @extend_schema(
        tags=["用户"],
        summary="用户登出",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("LogoutResponse"),
                description="登出成功",
            )
        },
    )
    def post(self, request):
        """用户登出"""
        logout(request)
        return APIResponse.success(message='已成功登出')


class TokenRefreshViewWithDocs(TokenRefreshView):
    """刷新访问令牌视图"""

    @extend_schema(
        tags=["用户"],
        summary="刷新访问令牌",
        request=token_refresh_request_serializer,
        responses={
            200: OpenApiResponse(
                response=token_refresh_response_serializer,
                description="刷新成功",
            ),
            401: OpenApiResponse(description="无效或过期的刷新令牌"),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(
    tags=["用户"],
    summary="获取当前登录用户信息",
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "CurrentUserResponse", current_user_data_serializer
            ),
            description="用户信息",
        ),
        401: OpenApiResponse(
            response=standard_error_response("CurrentUserUnauthorized"),
            description="未登录",
        ),
    },
)
@api_view(['GET'])
@ensure_csrf_cookie
@permission_classes([AllowAny])
def get_current_user(request):
    """获取当前登录用户信息"""
    if request.user.is_authenticated:
        # 获取用户所属的组
        groups = list(request.user.groups.values_list('name', flat=True))
        
        # 获取用户权限（用于前端权限控制）
        permissions = []
        if request.user.is_superuser:
            # 超级用户拥有所有权限
            permissions = ['*']
        else:
            # 获取用户的所有权限（包括通过组获得的权限）
            # 使用 get_all_permissions() 获取所有权限字符串（格式：app_label.codename）
            permissions = list(request.user.get_all_permissions())
        
        return APIResponse.success(data={
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
            'groups': groups,
            'is_salesperson': '业务员' in groups,
            'permissions': permissions,  # 添加权限列表
        })
    else:
        return APIResponse.error('未登录', code=status.HTTP_401_UNAUTHORIZED)


@extend_schema(
    tags=["用户"],
    summary="用户注册",
    request=register_request_serializer,
    responses={
        201: OpenApiResponse(
            response=standard_success_response(
                "RegisterResponse", register_data_serializer
            ),
            description="注册成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("RegisterBadRequest"),
            description="请求无效",
        ),
    },
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
        return APIResponse.error('请提供用户名和密码', code=status.HTTP_400_BAD_REQUEST)
    
    # 验证用户名格式（允许中文、字母、数字、下划线、连字符）
    if not re.match(r'^[\w\u4e00-\u9fa5-]+$', username):
        return APIResponse.error('用户名只能包含字母、数字、下划线、连字符和中文字符', code=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(username=username).exists():
        return APIResponse.error('用户名已存在', code=status.HTTP_400_BAD_REQUEST)
    
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name
    )
    
    # 自动登录
    login(request, user)
    
    return APIResponse.success(data={
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
    }, message='注册成功', code=status.HTTP_201_CREATED)


@extend_schema(
    tags=["用户"],
    summary="获取业务员列表",
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "SalespersonListResponse", UserSerializer, many=True
            ),
            description="业务员列表",
        ),
        500: OpenApiResponse(
            response=standard_error_response("SalespersonListError"),
            description="服务器错误",
        ),
    },
)
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
        return APIResponse.success(data=serializer.data)
    except Exception as e:
        return APIResponse.error(str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["用户"],
    summary="按部门获取用户列表",
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "DepartmentUserListResponse", UserSerializer, many=True
            ),
            description="用户列表",
        ),
        500: OpenApiResponse(
            response=standard_error_response("DepartmentUserListError"),
            description="服务器错误",
        ),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_users_by_department(request):
    """根据部门获取用户列表"""
    from .models import UserProfile

    try:
        department_id = request.query_params.get('department_id')

        # 获取所有活跃用户
        users = User.objects.filter(is_active=True).exclude(is_superuser=True)

        # 如果指定了部门，则过滤该部门的用户
        if department_id:
            users = users.filter(profile__departments__id=department_id).distinct()

        users = users.order_by('username')
        serializer = UserSerializer(users, many=True)
        return APIResponse.success(data=serializer.data)
    except Exception as e:
        return APIResponse.error(str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["用户"],
    summary="修改密码",
    request=change_password_request_serializer,
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ChangePasswordResponse"),
            description="修改成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ChangePasswordBadRequest"),
            description="请求无效",
        ),
        500: OpenApiResponse(
            response=standard_error_response("ChangePasswordServerError"),
            description="服务器错误",
        ),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """修改密码"""
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')

    # 验证参数
    if not old_password or not new_password or not confirm_password:
        return APIResponse.error('请提供旧密码、新密码和确认密码', code=status.HTTP_400_BAD_REQUEST)

    # 验证新密码和确认密码是否一致
    if new_password != confirm_password:
        return APIResponse.error('新密码和确认密码不一致', code=status.HTTP_400_BAD_REQUEST)

    # 验证旧密码是否正确
    if not request.user.check_password(old_password):
        return APIResponse.error('旧密码错误', code=status.HTTP_400_BAD_REQUEST)

    # 验证新密码长度
    if len(new_password) < 6:
        return APIResponse.error('新密码长度至少为6位', code=status.HTTP_400_BAD_REQUEST)

    # 修改密码
    try:
        request.user.set_password(new_password)
        request.user.save()
        return APIResponse.success(message='密码修改成功')
    except Exception as e:
        return APIResponse.error(f'密码修改失败: {str(e)}', code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["用户"],
    summary="更新个人信息",
    methods=["PUT", "PATCH"],
    request=update_profile_request_serializer,
    responses={
        200: OpenApiResponse(
            response=standard_success_response(
                "UpdateProfileResponse", update_profile_data_serializer
            ),
            description="更新成功",
        ),
        500: OpenApiResponse(
            response=standard_error_response("UpdateProfileServerError"),
            description="服务器错误",
        ),
    },
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """更新个人信息"""
    data = request.data

    try:
        # 更新允许修改的字段
        if 'email' in data:
            request.user.email = data['email']
        if 'first_name' in data:
            request.user.first_name = data['first_name']
        if 'last_name' in data:
            request.user.last_name = data['last_name']

        request.user.save()

        # 返回更新后的用户信息
        groups = list(request.user.groups.values_list('name', flat=True))
        permissions = ['*'] if request.user.is_superuser else list(request.user.get_all_permissions())

        return APIResponse.success(
            data={
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'is_staff': request.user.is_staff,
                'is_superuser': request.user.is_superuser,
                'groups': groups,
                'permissions': permissions,
            },
            message='个人信息更新成功',
        )
    except Exception as e:
        return APIResponse.error(f'个人信息更新失败: {str(e)}', code=status.HTTP_500_INTERNAL_SERVER_ERROR)

from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from datetime import timedelta
from .serializers import UserSerializer
from workorder.response import APIResponse
from workorder.schema import standard_error_response, standard_success_response
from workorder.constants.role_codes import SALES, resolve_role_codes
import re
import time


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
        "role_codes": serializers.ListField(child=serializers.CharField()),
        "departments": serializers.ListField(child=serializers.CharField()),
        "is_salesperson": serializers.BooleanField(),
        "permissions": serializers.ListField(child=serializers.CharField()),
        "access": serializers.CharField(),
        "refresh": serializers.CharField(),
        "access_expires_at": serializers.IntegerField(
            help_text="Access token expiration timestamp in seconds"
        ),
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
        "role_codes": serializers.ListField(child=serializers.CharField()),
        "departments": serializers.ListField(child=serializers.CharField()),
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
        "role_codes": serializers.ListField(child=serializers.CharField()),
        "departments": serializers.ListField(child=serializers.CharField()),
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
        "access_expires_at": serializers.IntegerField(
            help_text="Access token expiration timestamp in seconds"
        ),
    },
)


def _department_names(user):
    if not hasattr(user, "profile"):
        return []
    return list(user.profile.departments.values_list("name", flat=True))


def _get_access_token_expires_at():
    """获取 access token 过期时间戳（Unix timestamp）"""
    access_lifetime = settings.SIMPLE_JWT.get("ACCESS_TOKEN_LIFETIME", timedelta(minutes=5))
    # 将 timedelta 转换为秒
    expires_in_seconds = int(access_lifetime.total_seconds())
    return int(time.time()) + expires_in_seconds


def _build_user_data(user):
    """构建统一的用户信息字典，所有返回用户信息的接口均使用此函数，确保字段一致。"""
    group_names = list(user.groups.values_list("name", flat=True))
    role_codes = resolve_role_codes(group_names)
    departments = _department_names(user)
    permissions = ["*"] if user.is_superuser else list(user.get_all_permissions())
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "role_codes": role_codes,
        "departments": departments,
        "is_salesperson": SALES in role_codes,
        "permissions": permissions,
    }


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
                response=standard_success_response(
                    "LoginResponse", login_data_serializer
                ),
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
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return APIResponse.error(
                "请提供用户名和密码", code=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, username=username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)

            user_data = _build_user_data(user)
            user_data["access"] = str(refresh.access_token)
            user_data["refresh"] = str(refresh)
            user_data["access_expires_at"] = _get_access_token_expires_at()

            return APIResponse.success(data=user_data)
        else:
            return APIResponse.error(
                "用户名或密码错误", code=status.HTTP_401_UNAUTHORIZED
            )


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
        return APIResponse.success(message="已成功登出")


class AdminSessionView(APIView):
    """为 Django Admin 建立会话"""

    permission_classes = [IsAuthenticated]
    serializer_class = EmptySerializer

    @extend_schema(
        tags=["用户"],
        summary="创建 Django Admin 会话",
        responses={
            200: OpenApiResponse(description="会话创建成功"),
            403: OpenApiResponse(description="当前用户无后台权限"),
        },
    )
    def post(self, request):
        user = request.user
        if not user.is_staff:
            return APIResponse.error(
                "当前用户无管理后台权限", code=status.HTTP_403_FORBIDDEN
            )

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return APIResponse.success(
            data={"admin_url": "/admin/"},
            message="管理后台会话已创建",
        )


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
        # 调用父类获取原始 JWT 响应
        response = super().post(request, *args, **kwargs)
        # 包装为标准格式，并附加 access_expires_at
        if response.status_code == 200:
            return APIResponse.success(
                data={
                    **response.data,
                    "access_expires_at": _get_access_token_expires_at(),
                }
            )
        return response


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
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """获取当前登录用户信息"""
    if request.user.is_authenticated:
        return APIResponse.success(data=_build_user_data(request.user))
    else:
        return APIResponse.error("未登录", code=status.HTTP_401_UNAUTHORIZED)


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
@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    """用户注册"""
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email", "")
    first_name = request.data.get("first_name", "")
    last_name = request.data.get("last_name", "")

    if not username or not password:
        return APIResponse.error("请提供用户名和密码", code=status.HTTP_400_BAD_REQUEST)

    # 验证用户名格式（允许中文、字母、数字、下划线、连字符）
    if not re.match(r"^[\w\u4e00-\u9fa5-]+$", username):
        return APIResponse.error(
            "用户名只能包含字母、数字、下划线、连字符和中文字符",
            code=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username=username).exists():
        return APIResponse.error("用户名已存在", code=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )

    # 自动登录
    login(request, user)

    return APIResponse.success(
        data={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
        message="注册成功",
        code=status.HTTP_201_CREATED,
    )


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
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_salespersons(request):
    """获取业务员列表"""
    try:
        salesperson_group = Group.objects.filter(name=SALES).first()

        if salesperson_group:
            # 获取属于业务员组的用户
            salespersons = salesperson_group.user_set.filter(is_active=True).order_by(
                "username"
            )
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
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_users_by_department(request):
    """根据部门获取用户列表"""
    from .models import UserProfile

    try:
        department_id = request.query_params.get("department_id")

        # 获取所有活跃用户
        users = User.objects.filter(is_active=True).exclude(is_superuser=True)

        # 如果指定了部门，则过滤该部门的用户
        if department_id:
            users = users.filter(profile__departments__id=department_id).distinct()

        users = users.order_by("username")
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
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """修改密码"""
    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    # 验证参数
    if not old_password or not new_password or not confirm_password:
        return APIResponse.error(
            "请提供旧密码、新密码和确认密码", code=status.HTTP_400_BAD_REQUEST
        )

    # 验证新密码和确认密码是否一致
    if new_password != confirm_password:
        return APIResponse.error(
            "新密码和确认密码不一致", code=status.HTTP_400_BAD_REQUEST
        )

    # 验证旧密码是否正确
    if not request.user.check_password(old_password):
        return APIResponse.error("旧密码错误", code=status.HTTP_400_BAD_REQUEST)

    # 验证新密码长度
    if len(new_password) < 6:
        return APIResponse.error(
            "新密码长度至少为6位", code=status.HTTP_400_BAD_REQUEST
        )

    # 修改密码
    try:
        request.user.set_password(new_password)
        request.user.save()
        return APIResponse.success(message="密码修改成功")
    except Exception as e:
        return APIResponse.error(
            f"密码修改失败: {str(e)}", code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """更新个人信息"""
    data = request.data

    try:
        # 更新允许修改的字段
        if "email" in data:
            request.user.email = data["email"]
        if "first_name" in data:
            request.user.first_name = data["first_name"]
        if "last_name" in data:
            request.user.last_name = data["last_name"]

        request.user.save()

        return APIResponse.success(
            data=_build_user_data(request.user),
            message="个人信息更新成功",
        )
    except Exception as e:
        return APIResponse.error(
            f"个人信息更新失败: {str(e)}", code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

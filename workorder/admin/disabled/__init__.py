"""
未启用的 Admin 类

此目录包含暂时未启用到 Django Admin 的类。

这些类已经开发完成，但由于业务原因暂时未注册到 Admin。
如需启用，请将相应的类从本目录移回上级目录，并取消 @admin.register() 装饰器的注释。

模块：
- inventory: 库存管理相关 Admin（4个类）
- finance: 财务管理相关 Admin（3个类）
"""

# 默认不自动导入任何 Admin 类，避免注册到 Django Admin

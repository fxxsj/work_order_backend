"""
数据导出工具
支持 Excel 格式导出
"""
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime


def create_excel_response(filename):
    """创建 Excel HTTP 响应"""
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def style_header_cell(cell):
    """设置表头单元格样式"""
    if not OPENPYXL_AVAILABLE:
        return
    cell.font = Font(bold=True, color="FFFFFF", size=11)
    cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )


def style_data_cell(cell):
    """设置数据单元格样式"""
    if not OPENPYXL_AVAILABLE:
        return
    cell.alignment = Alignment(horizontal="left", vertical="center")
    cell.border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )


def export_work_orders(queryset, filename=None):
    """
    导出施工单列表到 Excel
    
    Args:
        queryset: 施工单查询集
        filename: 文件名（可选）
    
    Returns:
        HttpResponse: Excel 文件响应
    """
    if not OPENPYXL_AVAILABLE:
        from django.http import HttpResponse
        return HttpResponse(
            'Excel 导出功能需要安装 openpyxl 库。请运行: pip install openpyxl',
            status=500,
            content_type='text/plain; charset=utf-8'
        )
    
    if filename is None:
        filename = f'施工单列表_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    wb = Workbook()
    ws = wb.active
    ws.title = "施工单列表"
    
    # 表头
    headers = [
        '施工单号', '客户名称', '业务员', '创建人', '创建时间', '订单日期', 
        '交货日期', '状态', '审核状态', '优先级', '备注'
    ]
    
    # 写入表头
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        style_header_cell(cell)
    
    # 状态映射
    status_map = {
        'pending': '待开始',
        'in_progress': '进行中',
        'paused': '已暂停',
        'completed': '已完成',
        'cancelled': '已取消'
    }
    
    approval_status_map = {
        'pending': '待审核',
        'approved': '已审核',
        'rejected': '已拒绝'
    }
    
    priority_map = {
        'low': '低',
        'normal': '普通',
        'high': '高',
        'urgent': '紧急'
    }
    
    # 写入数据
    for row_num, work_order in enumerate(queryset, 2):
        ws.cell(row=row_num, column=1, value=work_order.order_number)
        ws.cell(row=row_num, column=2, value=work_order.customer.name if work_order.customer else '')
        ws.cell(row=row_num, column=3, value=work_order.customer.salesperson.username if work_order.customer and work_order.customer.salesperson else '')
        ws.cell(row=row_num, column=4, value=work_order.created_by.username if work_order.created_by else '')
        ws.cell(row=row_num, column=5, value=work_order.created_at.strftime('%Y-%m-%d %H:%M:%S') if work_order.created_at else '')
        ws.cell(row=row_num, column=6, value=work_order.order_date.strftime('%Y-%m-%d') if work_order.order_date else '')
        ws.cell(row=row_num, column=7, value=work_order.delivery_date.strftime('%Y-%m-%d') if work_order.delivery_date else '')
        ws.cell(row=row_num, column=8, value=status_map.get(work_order.status, work_order.status))
        ws.cell(row=row_num, column=9, value=approval_status_map.get(work_order.approval_status, work_order.approval_status))
        ws.cell(row=row_num, column=10, value=priority_map.get(work_order.priority, work_order.priority))
        ws.cell(row=row_num, column=11, value=work_order.notes or '')
        
        # 设置数据单元格样式
        for col_num in range(1, len(headers) + 1):
            style_data_cell(ws.cell(row=row_num, column=col_num))
    
    # 调整列宽
    column_widths = [18, 20, 12, 12, 20, 12, 12, 10, 10, 10, 30]
    for col_num, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(col_num)].width = width
    
    # 冻结首行
    ws.freeze_panes = 'A2'
    
    # 创建响应
    response = create_excel_response(filename)
    wb.save(response)
    return response


def export_tasks(queryset, filename=None):
    """
    导出任务列表到 Excel
    
    Args:
        queryset: 任务查询集
        filename: 文件名（可选）
    
    Returns:
        HttpResponse: Excel 文件响应
    """
    if not OPENPYXL_AVAILABLE:
        from django.http import HttpResponse
        return HttpResponse(
            'Excel 导出功能需要安装 openpyxl 库。请运行: pip install openpyxl',
            status=500,
            content_type='text/plain; charset=utf-8'
        )
    
    if filename is None:
        filename = f'任务列表_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    wb = Workbook()
    ws = wb.active
    ws.title = "任务列表"
    
    # 表头
    headers = [
        '施工单号', '工序', '任务类型', '工作内容', '分派部门', '分派操作员',
        '生产数量', '完成数量', '不良品数量', '状态', '创建时间', '更新时间', '备注'
    ]
    
    # 写入表头
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        style_header_cell(cell)
    
    # 状态映射
    status_map = {
        'pending': '待开始',
        'in_progress': '进行中',
        'completed': '已完成',
        'cancelled': '已取消',
        'skipped': '已跳过'
    }
    
    task_type_map = {
        'general': '通用',
        'artwork': '制版',
        'cutting': '开料',
        'printing': '印刷',
        'foiling': '烫金',
        'embossing': '压凸',
        'die_cutting': '模切',
        'packaging': '包装'
    }
    
    # 写入数据
    for row_num, task in enumerate(queryset, 2):
        work_order = task.work_order_process.work_order
        process = task.work_order_process.process
        
        ws.cell(row=row_num, column=1, value=work_order.order_number)
        ws.cell(row=row_num, column=2, value=process.name if process else '')
        ws.cell(row=row_num, column=3, value=task_type_map.get(task.task_type, task.task_type))
        ws.cell(row=row_num, column=4, value=task.work_content or '')
        ws.cell(row=row_num, column=5, value=task.assigned_department.name if task.assigned_department else '')
        ws.cell(row=row_num, column=6, value=task.assigned_operator.username if task.assigned_operator else '')
        ws.cell(row=row_num, column=7, value=task.production_quantity or '')
        ws.cell(row=row_num, column=8, value=task.quantity_completed or 0)
        ws.cell(row=row_num, column=9, value=task.quantity_defective or 0)
        ws.cell(row=row_num, column=10, value=status_map.get(task.status, task.status))
        ws.cell(row=row_num, column=11, value=task.created_at.strftime('%Y-%m-%d %H:%M:%S') if task.created_at else '')
        ws.cell(row=row_num, column=12, value=task.updated_at.strftime('%Y-%m-%d %H:%M:%S') if task.updated_at else '')
        ws.cell(row=row_num, column=13, value=task.production_requirements or '')
        
        # 设置数据单元格样式
        for col_num in range(1, len(headers) + 1):
            style_data_cell(ws.cell(row=row_num, column=col_num))
    
    # 调整列宽
    column_widths = [18, 15, 10, 30, 15, 12, 12, 12, 12, 10, 20, 20, 30]
    for col_num, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(col_num)].width = width
    
    # 冻结首行
    ws.freeze_panes = 'A2'
    
    # 创建响应
    response = create_excel_response(filename)
    wb.save(response)
    return response


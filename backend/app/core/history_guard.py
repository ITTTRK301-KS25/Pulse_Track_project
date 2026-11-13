"""B17: lịch sử append-only ở tầng ORM. Mọi UPDATE/DELETE một dòng task_history qua session đều bị chặn.

Chỉ cần import module này một lần (api/history.py đã import). Xóa dây chuyền khi xóa task/dự án do
khóa ngoại ON DELETE CASCADE của MySQL xử lý, không đi qua ORM nên không bị chặn.
"""
from sqlalchemy import event

from app.models.task_history import TaskHistory


class HistoryImmutableError(RuntimeError):
    pass


@event.listens_for(TaskHistory, "before_update")
def _block_update(mapper, connection, target):
    raise HistoryImmutableError("task_history chỉ thêm, không được sửa")


@event.listens_for(TaskHistory, "before_delete")
def _block_delete(mapper, connection, target):
    raise HistoryImmutableError("task_history chỉ thêm, không được xóa")

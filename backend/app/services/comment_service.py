"""B15 + B16: bình luận của task.

Thêm (B15): OWNER/MEMBER; VIEWER và người ngoài dự án -> 403; dự án hoặc task đã lưu trữ -> 409;
            task không thuộc dự án trong đường dẫn -> 404.
Đọc (B16): mọi thành viên dự án (kể cả VIEWER) đọc được, kể cả task đã lưu trữ.
            Sắp theo created_at tăng dần, trùng thời gian thì theo id tăng dần; kèm tên tác giả.
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.comment import Comment
from app.models.task import Task
from app.models.user import User
from app.services import project_access as access
from app.services.task_history_service import _iso


def _comment_to_dict(c: Comment, author_name: str) -> dict:
    return {
        "id": c.id,
        "task_id": c.task_id,
        "project_id": c.project_id,
        "author_id": c.author_id,
        "author_name": author_name,
        "content": c.content,
        "created_at": _iso(c.created_at),
    }


def _task_in_project(db: Session, project_id: int, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy task trong dự án này")
    return task


def create_comment(db: Session, user: User, project_id: int, task_id: int, content: str) -> dict:
    project, role = access.get_project_and_role(db, project_id, user, lock=True)
    access.require(role, "task.write")
    access.require_active(project)
    task = _task_in_project(db, project_id, task_id)
    db.refresh(task)
    if task.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task đã lưu trữ, không thể bình luận")
    try:
        comment = Comment(task_id=task.id, project_id=project_id, author_id=user.id, content=content)
        db.add(comment)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(comment)
    return _comment_to_dict(comment, user.display_name)


def list_comments(db: Session, user: User, project_id: int, task_id: int) -> list[dict]:
    _, role = access.get_project_and_role(db, project_id, user)
    access.require(role, "project.read")
    _task_in_project(db, project_id, task_id)
    rows = db.execute(
        select(Comment, User.display_name)
        .join(User, User.id == Comment.author_id)
        .where(Comment.task_id == task_id, Comment.project_id == project_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
    ).all()
    return [_comment_to_dict(c, name) for c, name in rows]

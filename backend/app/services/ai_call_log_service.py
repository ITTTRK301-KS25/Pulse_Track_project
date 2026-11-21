"""A07: ghi metadata AI bằng transaction riêng, tách khỏi nghiệp vụ gọi AI."""
from app.ai.adapter import AICallRecord
from app.database.db import SessionLocal
from app.models.ai_call_log import AICallLog


def make_ai_call_recorder(project_id: int, actor_id: int):
    def record_ai_call(record: AICallRecord) -> None:
        db = SessionLocal()
        try:
            db.add(
                AICallLog(
                    project_id=project_id,
                    actor_id=actor_id,
                    request_id=record.request_id,
                    type=record.type,
                    status=record.status,
                    error_code=record.error_code,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return record_ai_call

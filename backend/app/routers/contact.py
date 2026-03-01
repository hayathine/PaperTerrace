"""
お問い合わせ・要望受付ルーター。

フロー:
  1. Cloud SQL (PostgreSQL) の contact_requests テーブルへ永続化
  2. DB 保存成功をトリガーに BackgroundTasks で Gmail 送信
     → API レスポンスはメール送信完了を待たずに即返却
"""

import os
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm.contact import ContactRequest as ContactRequestORM
from app.schemas.contact import ContactRequest
from common.logger import logger

router = APIRouter(prefix="/contact", tags=["Contact"])

DESTINATION_EMAIL = "gwsgsgdas@gmail.com"


def _send_email(record_id: str, req: ContactRequest) -> None:
    """
    DB 保存後にバックグラウンドで呼ばれるメール送信処理。
    送信結果は mail_status カラムへ反映する。
    環境変数 SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD が未設定の場合はスキップ。
    """

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        logger.warning(
            "SMTP credentials not configured. Email skipped.",
            record_id=record_id,
        )
        _update_mail_status(record_id, "skipped")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[PaperTerrace] 要望・お問い合わせ from {req.name}"
    msg["From"] = smtp_user
    msg["To"] = DESTINATION_EMAIL
    msg["Reply-To"] = req.email

    body = (
        f"差出人: {req.name} <{req.email}>\n\n"
        f"--- メッセージ ---\n{req.message}\n\n"
        f"record_id: {record_id}"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, DESTINATION_EMAIL, msg.as_string())
        logger.info("Contact email sent successfully", record_id=record_id)
        _update_mail_status(record_id, "sent")
    except smtplib.SMTPException as exc:
        logger.error("Failed to send contact email", record_id=record_id, error=str(exc))
        _update_mail_status(record_id, "failed")


def _update_mail_status(record_id: str, status: str) -> None:
    """メール送信結果を DB に反映する。"""
    from app.database import get_db_context

    try:
        with get_db_context() as db:
            record = db.query(ContactRequestORM).filter_by(id=record_id).first()
            if record:
                record.mail_status = status
                db.commit()
    except Exception as exc:
        logger.error("Failed to update mail_status", record_id=record_id, error=str(exc))


@router.post("", summary="要望・お問い合わせを受け付ける")
async def submit_contact(
    req: ContactRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    1. Cloud SQL (contact_requests テーブル) へ保存
    2. DB 保存成功をトリガーに BackgroundTasks でメール送信
    クライアントにはメール完了を待たず即座にレスポンスを返す。
    """
    record_id = str(uuid.uuid4())
    record = ContactRequestORM(
        id=record_id,
        name=req.name,
        email=req.email,
        message=req.message,
        mail_status="pending",
    )

    try:
        db.add(record)
        db.commit()
        logger.info("Contact request saved to DB", record_id=record_id, name=req.name)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to save contact request", error=str(exc))
        raise HTTPException(status_code=500, detail="要望の保存に失敗しました。") from exc

    # DB 保存成功をトリガーにメール送信をキュー
    background_tasks.add_task(_send_email, record_id, req)

    return {"status": "ok", "message": "要望を受け付けました。ありがとうございます。"}

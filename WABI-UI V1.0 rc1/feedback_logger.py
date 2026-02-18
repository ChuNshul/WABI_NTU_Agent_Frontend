# -*- coding: utf-8 -*-
"""
feedback_logger.py — 用户反馈记录模块

用于记录纠错意图的用户反馈，保存到 CSV 文件
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


# CSV 文件路径
FEEDBACK_CSV_PATH = Path(__file__).parent / "user_feedback.csv"


# CSV 表头
FEEDBACK_HEADERS = [
    "timestamp",           # 时间戳
    "patient_id",          # 用户ID
    "session_id",          # 会话ID
    "correction_input",    # 用户的纠错输入
    "previous_intent",     # 上一轮意图
    "previous_response",   # 上一轮AI回复
    "feedback_type",       # 反馈类型（具体错误/重新解释/其他）
    "feedback_content",    # 反馈内容
    "chat_history",        # 对话历史摘要
]


def _ensure_csv_exists():
    """确保 CSV 文件存在，如果不存在则创建并写入表头"""
    if not FEEDBACK_CSV_PATH.exists():
        with open(FEEDBACK_CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(FEEDBACK_HEADERS)


def log_correction_feedback(
    patient_id: str,
    correction_input: str,
    previous_intent: Optional[str],
    previous_response: Optional[str],
    feedback_type: str = "correction",
    feedback_content: str = "",
    chat_history: str = "",
    session_id: str = "",
) -> bool:
    """
    记录纠错反馈到 CSV 文件
    
    Args:
        patient_id: 用户ID
        correction_input: 用户的纠错输入（如"不对"、"错了"等）
        previous_intent: 上一轮意图
        previous_response: 上一轮AI回复摘要
        feedback_type: 反馈类型
        feedback_content: 反馈内容
        chat_history: 对话历史摘要
        session_id: 会话ID
        
    Returns:
        是否成功记录
    """
    try:
        _ensure_csv_exists()
        
        timestamp = datetime.now().isoformat()
        
        row = [
            timestamp,
            patient_id,
            session_id,
            correction_input,
            previous_intent or "",
            previous_response or "",
            feedback_type,
            feedback_content,
            chat_history,
        ]
        
        with open(FEEDBACK_CSV_PATH, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)
        
        print(f"[FeedbackLogger] 反馈已记录: {patient_id} - {correction_input}")
        return True
        
    except Exception as e:
        print(f"[FeedbackLogger] 记录反馈失败: {e}")
        return False


def get_feedback_stats() -> Dict[str, Any]:
    """
    获取反馈统计信息
    
    Returns:
        统计信息字典
    """
    try:
        if not FEEDBACK_CSV_PATH.exists():
            return {"total": 0, "by_type": {}}
        
        total = 0
        by_type = {}
        
        with open(FEEDBACK_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                feedback_type = row.get("feedback_type", "unknown")
                by_type[feedback_type] = by_type.get(feedback_type, 0) + 1
        
        return {
            "total": total,
            "by_type": by_type,
            "file_path": str(FEEDBACK_CSV_PATH),
        }
        
    except Exception as e:
        print(f"[FeedbackLogger] 获取统计失败: {e}")
        return {"total": 0, "by_type": {}, "error": str(e)}


def read_recent_feedback(limit: int = 10) -> list:
    """
    读取最近的反馈记录
    
    Args:
        limit: 返回记录数量
        
    Returns:
        反馈记录列表
    """
    try:
        if not FEEDBACK_CSV_PATH.exists():
            return []
        
        records = []
        with open(FEEDBACK_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
        
        # 返回最近的记录
        return records[-limit:]
        
    except Exception as e:
        print(f"[FeedbackLogger] 读取反馈失败: {e}")
        return []


def update_feedback_content(
    patient_id: str,
    feedback_content: str,
    timestamp: str = None
) -> bool:
    """
    更新最近一条反馈记录的内容
    
    如果没有找到匹配的记录，创建一条新记录
    
    Args:
        patient_id: 用户ID
        feedback_content: 用户提交的反馈内容
        timestamp: 可选，指定要更新的记录时间戳
        
    Returns:
        是否成功更新
    """
    try:
        _ensure_csv_exists()
        
        records = []
        updated = False
        # 始终使用标准表头
        fieldnames = FEEDBACK_HEADERS
        
        # 读取现有记录
        if FEEDBACK_CSV_PATH.exists():
            with open(FEEDBACK_CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # 读取时使用文件中的表头，但写入时使用标准表头
                file_fieldnames = reader.fieldnames or FEEDBACK_HEADERS
                for row in reader:
                    # 确保每一行都有所有标准字段
                    for field in FEEDBACK_HEADERS:
                        if field not in row:
                            row[field] = ""
                    records.append(row)
        
        # 从后往前找，更新最近一条匹配的记录
        for row in reversed(records):
            if row.get("patient_id") == patient_id:
                if timestamp is None or row.get("timestamp") == timestamp:
                    row["feedback_content"] = feedback_content
                    updated = True
                    print(f"[FeedbackLogger] 更新反馈内容: {patient_id}")
                    break
        
        # 如果没有找到匹配的记录，创建新记录
        if not updated:
            new_record = {field: "" for field in FEEDBACK_HEADERS}
            new_record["timestamp"] = datetime.now().isoformat()
            new_record["patient_id"] = patient_id
            new_record["feedback_type"] = "manual_feedback"
            new_record["feedback_content"] = feedback_content
            records.append(new_record)
            updated = True
            print(f"[FeedbackLogger] 创建新反馈记录: {patient_id}")
        
        # 写回文件，使用标准表头
        with open(FEEDBACK_CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FEEDBACK_HEADERS)
            writer.writeheader()
            # 只写入标准表头中的字段
            standard_records = []
            for row in records:
                standard_row = {field: row.get(field, "") for field in FEEDBACK_HEADERS}
                standard_records.append(standard_row)
            writer.writerows(standard_records)
        
        return updated
        
    except Exception as e:
        print(f"[FeedbackLogger] 更新反馈失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 测试
    log_correction_feedback(
        patient_id="test_user",
        correction_input="不对",
        previous_intent="food_recognition",
        previous_response="识别出红烧鸡...",
        feedback_type="correction",
        feedback_content="食物识别错误",
        chat_history="用户上传图片->AI识别->用户纠正",
    )
    
    print("统计:", get_feedback_stats())
    print("最近记录:", read_recent_feedback(5))

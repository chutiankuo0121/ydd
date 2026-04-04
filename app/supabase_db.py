"""
Supabase 数据库操作模块
保存邮箱到 outlook 或 hotmail 表
"""
from datetime import datetime
from functools import lru_cache

from supabase import Client, create_client

# Supabase 配置
SUPABASE_URL = "https://cplxgurubfvncnmpmpdp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNwbHhndXJ1YmZ2bmNubXBtcGRwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg3ODAwOTgsImV4cCI6MjA4NDM1NjA5OH0.CwpSegDn5O_EG04YHoE478cvhTDwPTALYY6n6Z35hJw"


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def save_email(email: str, password: str, refresh_token: str = None, client_id: str = None):
    """
    根据邮箱域名保存到对应表
    outlook.com -> outlook 表
    hotmail.com -> hotmail 表
    """
    # 提取域名
    if '@' in email:
        domain = email.split('@')[1].lower()
    else:
        domain = 'outlook.com'
    
    # 判断表名
    if domain == 'hotmail.com':
        table_name = 'hotmail'
    else:
        table_name = 'outlook'
    
    # 准备数据
    data = {
        '邮箱': email,
        '密码': password,
        '注册时间': datetime.now().isoformat()
    }
    
    # 可选字段
    if refresh_token:
        data['refresh_token'] = refresh_token
    if client_id:
        data['client_id'] = client_id
    
    try:
        # 插入数据，遇到重复邮箱则更新
        get_supabase_client().table(table_name).upsert(data).execute()
        print(f"[Supabase] 已保存到 {table_name} 表: {email}")
        return True
    except Exception as e:
        print(f"[Supabase Error] 保存失败: {e}")
        return False

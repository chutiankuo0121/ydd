"""
测试 Microsoft Graph API 调用
从 Supabase 读取账号并尝试调用 API
"""
import os
from curl_cffi import requests as curl_requests
from supabase_db import get_supabase_client

# SSL验证配置
TEST_VERIFY_SSL = os.getenv("TEST_VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no"}


def get_first_account(table_name='outlook'):
    """从 Supabase 获取第一个账号"""
    try:
        supabase = get_supabase_client()
        result = supabase.table(table_name).select('*').limit(1).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        print(f"[Error] 读取 {table_name} 失败: {e}")
        return None

# 尝试刷新 token
def try_refresh(refresh_token, client_id, tenant='common'):
    """尝试刷新 token 获取 access_token"""
    url = f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
    
    # 和 mail_service.py 一致：默认不传 scope，除非环境变量设置
    data = {
        'client_id': client_id,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }
    
    extra_scope = os.getenv("OUTLOOK_TOKEN_SCOPE", "").strip()
    if extra_scope:
        data['scope'] = extra_scope
    
    response = curl_requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=TEST_VERIFY_SSL,
        timeout=30,
        impersonate="safari",
    )
    return response.status_code, response.json()

def test_graph_api(access_token):
    """测试 Microsoft Graph API 调用"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    response = curl_requests.get(
        'https://graph.microsoft.com/v1.0/me',
        headers=headers,
        verify=TEST_VERIFY_SSL,
        timeout=30,
        impersonate="safari"
    )
    return response.status_code, response.json()


def test_email_api(access_token):
    """测试获取邮件列表"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    params = {
        '$select': 'id,subject,body,from,receivedDateTime',
        '$orderby': 'receivedDateTime desc',
        '$top': '1',
    }
    response = curl_requests.get(
        'https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages',
        params=params,
        headers=headers,
        verify=TEST_VERIFY_SSL,
        timeout=30,
        impersonate="safari"
    )
    return response.status_code, response.json()


def main():
    # 尝试两个表
    tables = ['outlook', 'hotmail']
    account = None
    table_name = None
    
    for tbl in tables:
        account = get_first_account(tbl)
        if account:
            table_name = tbl
            break
    
    if not account:
        print("[Error] Supabase 中没有找到账号")
        return
    
    print(f"[Info] 使用 {table_name} 表账号: {account.get('邮箱')}")
    print(f"[Info] Client ID: {account.get('client_id', '未设置')}")
    print()
    
    refresh_token = account.get('refresh_token')
    client_id = account.get('client_id')
    
    if not refresh_token:
        print("[Error] 该账号没有 refresh_token，需要重新获取 OAuth")
        return
    
    if not client_id:
        client_id = "c5e63ca4-b1ce-4640-ba79-7dee38d07db4"
        print(f"[Warning] 账号没有 client_id，尝试使用默认值: {client_id}")
    
    # 尝试刷新 token
    print("[Test] 尝试刷新 token...")
    status, result = try_refresh(refresh_token, client_id)
    
    if status != 200 or 'access_token' not in result:
        error = result.get('error_description', result.get('error', '未知错误'))
        print(f"[FAIL] Token 刷新失败: {error}")
        print("\n[结论] Token 无效或过期，需要重新授权")
        return
    
    access_token = result['access_token']
    print(f"[OK] Token 刷新成功")
    print(f"     Access Token: {access_token[:30]}...")
    print(f"     过期时间: {result.get('expires_in', 'N/A')} 秒")
    print()
    
    # 测试 Graph API
    print("[Test] 测试 Microsoft Graph API (获取用户信息)...")
    status, user_info = test_graph_api(access_token)
    
    if status == 200:
        print(f"[OK] API 调用成功!")
        print(f"     用户: {user_info.get('displayName', 'N/A')}")
        print(f"     邮箱: {user_info.get('mail', user_info.get('userPrincipalName', 'N/A'))}")
    else:
        error = user_info.get('error', {}).get('message', '未知错误')
        print(f"[FAIL] API 调用失败: {error}")
        return
    
    print()
    
    # 测试邮件 API
    print("[Test] 测试邮件 API (获取收件箱)...")
    status, emails = test_email_api(access_token)
    
    if status == 200:
        count = len(emails.get('value', []))
        print(f"[OK] 邮件 API 调用成功!")
        print(f"     获取到 {count} 封邮件")
        if count > 0:
            first = emails['value'][0]
            print(f"     最新邮件: {first.get('subject', '无主题')}")
    else:
        error = emails.get('error', {}).get('message', '未知错误')
        print(f"[FAIL] 邮件 API 调用失败: {error}")
    
    print("\n" + "="*60)
    print("[结论] 全部测试通过! API 可以正常调用")
    print("="*60)

if __name__ == "__main__":
    main()

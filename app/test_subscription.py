#!/usr/bin/env python3
"""测试机场订阅获取"""

import sys
import os

# 添加项目路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from airport.subscription import load_airport_nodes, CLASH_USER_AGENT

# 测试订阅 URL
TEST_SUBSCRIPTION_URL = "https://156.226.174.149/api/v1/client/subscribe?token=f906e9d46105a06acb10c81a6899b2fe"


def test_subscription():
    print("=" * 50)
    print("机场订阅获取测试")
    print("=" * 50)
    print(f"订阅 URL: {TEST_SUBSCRIPTION_URL}")
    print(f"User-Agent: {CLASH_USER_AGENT}")
    print("-" * 50)
    
    try:
        print("\n[1] 正在获取订阅节点...")
        nodes = load_airport_nodes(TEST_SUBSCRIPTION_URL)
        
        print(f"\n✓ 成功获取 {len(nodes)} 个节点")
        print("\n节点列表:")
        print("-" * 50)
        
        for i, node in enumerate(nodes, 1):
            print(f"{i}. {node.name}")
            print(f"   地址: {node.address}:{node.port}")
            print(f"   方法: {node.method}")
            if node.plugin:
                print(f"   插件: {node.plugin} ({node.plugin_mode})")
            print()
        
        print("-" * 50)
        print("✓ 测试通过！订阅获取正常")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print("\n详细错误:")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_subscription()
    sys.exit(0 if success else 1)

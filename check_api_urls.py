#!/usr/bin/env python3
"""
Script to check api_url fields in results.json
"""
import re

def check_api_urls():
    with open('D:\\ASTDATA\\results.json', 'r', encoding='utf-8') as f:
        content = f.read()

    # 使用正则表达式快速扫描所有api_url字段
    pattern = r'"api_url":\s*([^,\n}]*)'
    matches = re.findall(pattern, content)

    null_count = sum(1 for m in matches if m.strip() == 'null')
    non_null_matches = [m.strip() for m in matches if m.strip() != 'null']

    print(f'总共找到 {len(matches)} 个api_url字段')
    print(f'其中为null的数量: {null_count}')
    print(f'其中非null的数量: {len(non_null_matches)}')

    if non_null_matches:
        print('\n非null的api_url值:')
        for i, match in enumerate(non_null_matches[:10]):  # 只显示前10个
            print(f"{i+1}. {match}")
        if len(non_null_matches) > 10:
            print(f"... 还有 {len(non_null_matches) - 10} 个")
    else:
        print('\n没有找到非null的api_url值')

if __name__ == "__main__":
    check_api_urls()
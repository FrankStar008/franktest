#!/usr/bin/env python3
"""将文件中的英文引号替换为中文引号。

用法：
    python fix_quotes.py <文件路径>
    python fix_quotes.py 4_草稿/正文_v1_20260604.md

替换规则：
    英文直引号 "..." → 中文引号 "..."
    英文直单引号 '...' → 中文引号 '...'
    已有中文引号的不重复处理
"""

import sys
import re
from pathlib import Path


def convert_quotes(text: str) -> str:
    result = []
    double_open = False
    single_open = False

    for char in text:
        if char == '"':
            if double_open:
                result.append('”')  # "
                double_open = False
            else:
                result.append('“')  # "
                double_open = True
        elif char == "'":
            # 跳过缩写中的撇号（前一个字符是字母时视为撇号，不转换）
            if result and result[-1].isalpha():
                result.append(char)
            elif single_open:
                result.append('’')  # '
                single_open = False
            else:
                result.append('‘')  # '
                single_open = True
        else:
            result.append(char)

    return ''.join(result)


def main():
    if len(sys.argv) < 2:
        print("用法：python fix_quotes.py <文件路径>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"错误：文件不存在：{path}")
        sys.exit(1)

    original = path.read_text(encoding='utf-8')
    converted = convert_quotes(original)

    if original == converted:
        print("✅ 未发现需要替换的英文引号")
        return

    # 统计替换数量
    double_count = original.count('"')
    single_count = sum(1 for i, c in enumerate(original)
                       if c == "'" and (i == 0 or not original[i-1].isalpha()))

    path.write_text(converted, encoding='utf-8')
    print(f"✅ 引号统一完成：替换双引号 {double_count} 处，单引号 {single_count} 处")
    print(f"   文件已更新：{path}")


if __name__ == '__main__':
    main()

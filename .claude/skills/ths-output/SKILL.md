---
name: ths-output
description: |
  MBA毕业论文输出助手。将 4_草稿/ 下最新的正文 Markdown，按照
  1_开题/论文模板.docx 的格式，转换为排版正确的 Word 文件并保存到 5_输出/。

  触发词：「输出论文」「生成 Word」「导出 docx」「ths-output」
  「帮我生成最终文档」「把草稿转成 Word」「输出最终版」
---

# ths-output：论文输出

## 第零步：告诉用户任务基本预期

任务开始时，输出：

```
=================
任务：论文格式输出（ths-output）

目标：将最新正文草稿转换为符合模板格式的 Word 文件

步骤：
  1. 定位输入文件（正文草稿 + 论文模板）
  2. 检查依赖（python-docx）
  3. 执行格式转换
  4. 保存到 5_输出/

大约需要时间：2-5 分钟
=================
```

---

## 第一步：定位文件（进度 1/4）

### 1.1 找最新正文草稿

```python
from pathlib import Path
import re

drafts = list(Path("4_草稿").glob("正文_*.md"))
if not drafts:
    # 宽泛搜索：任何 md 文件
    drafts = list(Path("4_草稿").glob("*.md"))

# 优先按文件名中的日期排序，其次按修改时间
def sort_key(p):
    m = re.search(r"(\d{8})", p.name)
    return m.group(1) if m else p.stat().st_mtime_ns

latest_draft = sorted(drafts, key=sort_key, reverse=True)[0] if drafts else None
print(f"最新正文：{latest_draft}")
```

如果 `4_草稿/` 中没有任何 `.md` 文件，**停止并告知用户**：
> 「未找到正文草稿，请先用 `/ths-write-now` 完成正文撰写。」

### 1.2 找论文模板

按以下优先级查找模板：

1. `1_开题/论文模板.docx`（ths-init 复制的学校模板）
2. `1_开题/*.docx`（目录下任意 docx）
3. `${CLAUDE_SKILL_DIR}/../ths-init/material/论文模板.docx`（内置默认）

```python
from pathlib import Path

candidates = [
    Path("1_开题/论文模板.docx"),
    *Path("1_开题").glob("*.docx"),
]
template = next((p for p in candidates if p.exists()), None)

if not template:
    # fallback 到 ths-init 内置模板
    skill_dir = Path(__file__).parent.parent  # ths-output 目录
    template = skill_dir.parent / "ths-init" / "material" / "论文模板.docx"

print(f"使用模板：{template}")
```

告知用户定位结果：

```
**任务进度（1/4）**
- 正文草稿：4_草稿/{文件名}（{字数} 字）
- 论文模板：{模板路径}
```

---

## 第二步：检查依赖（进度 2/4）

```python
try:
    import docx
    print("✅ python-docx 已安装")
except ImportError:
    import subprocess
    print("安装 python-docx …")
    subprocess.run(["pip", "install", "python-docx"], check=True)
    print("✅ 安装完成")
```

告知用户：`**任务进度（2/4）** 依赖检查通过`

---

## 第三步：执行格式转换（进度 3/4）

确定输出文件名：

```python
from datetime import date
today = date.today().strftime("%Y%m%d")
output_path = Path("5_输出") / f"论文正文_{today}.docx"
Path("5_输出").mkdir(exist_ok=True)
```

调用转换脚本（注意：参考文献内容已包含在正文 Markdown 中，无需额外传入）：

```bash
python "${CLAUDE_SKILL_DIR}/scripts/md_to_docx.py" \
  "4_草稿/{最新正文文件名}" \
  "{模板路径}" \
  "5_输出/论文正文_{今日日期}.docx"
```

脚本执行过程中会打印进度行，逐行展示给用户。

告知用户：`**任务进度（3/4）** 格式转换完成`

---

## 第四步：完成汇报（进度 4/4）

```
## 论文输出完成
----

**输出文件**：5_输出/论文正文_{今日日期}.docx
**来源草稿**：4_草稿/{文件名}
**使用模板**：{模板路径}

### 注意事项
- 封面已保留，请在 Word 中填写姓名、学号、导师等信息
- 目录已保留，在 Word 中右键目录 → 「更新域」可自动更新页码
- 图片未自动导入，图片位置已留有 `[⚠️ 此处为表格，请在 Word 中手动插入]` 占位符
- 建议在 Word 中逐章核查标题层级与缩进是否正确

### 下一步建议
- 在 Word 中检查标题层级与编号是否正确
- 在 Word 中插入参考图例
- 核对参考文献格式（GBT-7714-2015）
```

---

## Gotchas

- **预期控制**：每完成一步，告诉用户当前进度，如 "**任务进度(5/10)**"
- **字数统计**：`len(text)` 中文字符计1字，可用 `len(re.sub(r'\s', '', text))` 估算
- **脚本路径**：`${CLAUDE_SKILL_DIR}` 为当前 skill 的目录，通过 `Path(__file__).parent` 获取
- **模板保留逻辑**：脚本保留封面、原创声明、目录，仅替换摘要/Abstract/正文/参考文献区域的占位内容；若格式异常，检查模板中 `标题 1*` 样式的关键段落是否被修改过
- **图片**：当前版本不处理 Markdown 中的 `![]()` 图片语法，转换后需手动插入；图片位置会以 `[图片：{alt}]` 占位符标注
- **【疑似幻觉】标注**：正文中如有 `【疑似幻觉：请核实】` 标注，会原样保留在 Word 中，方便定位后手动处理

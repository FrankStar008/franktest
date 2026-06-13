---
name: ths-paper-load
description: |
  MBA毕业论文文献整理助手。将文献纳入
  参考文献列表.xml，匹配本地 PDF，读取内容生成摘要和研究关联，并生成待办汇报。

  使用时机：
  「整理文献」「纳管文献」「处理参考文献」「帮我整理文献」
  用户提供了开题报告文件路径（PDF/Word/Markdown）
  「参考文献文件夹有新文件」「补全文献信息」「处理新增的文献」
  用户贴出单条 cite 或网页链接

  不适用于：检索新文献（用 ths-paper-search）
---

# ths-paper-load

## 架构说明

处理文献时采用**主 agent 调度 + subagent 并行**架构：

- **主 agent**：解析引用列表、匹配 PDF、分批调度、收集结果、写入 XML、生成汇报
- **subagent（每批 5 篇并行）**：每个 subagent 处理多篇文献，读取内容，返回 JSON 数组
- **XML 写入只在主 agent 进行**：避免并发冲突

管理程序路径：`${CLAUDE_SKILL_DIR}/scripts/literature_manager.py`

---

## 入口判断

| 输入 | 模式 |
|------|------|
| 未指定 cite 或 URL | **模式 A**：从格式化列表整理 |
| 贴出单条 cite 字符串或 URL | **模式 B**：单条处理 |

---

## 第零步：找到论文主题

按以下优先级获取：
1. 读取 `CLAUDE.md`，查找「研究课题」「论文题目」「研究方向」相关段落
2. 从用户本次输入提取
3. 以上都没有 → 询问用户

将课题记录为 `RESEARCH_TOPIC`，传递给每个 subagent。


输出任务将信息：

```
=================
任务：导入已有文献（ths-paper-load）

目标：Agent 读取所有引用文献，提取摘要，供后续写作。

大约需要时间：N 分钟；
=================

```

如果模式A：30-40分钟
如果模式B：10-20分钟；

---

## 模式 A：从格式化列表整理

### A - 步骤1： 解析格式化列表

读取 `2_参考文献/格式化参考文献列表.md`，按 GBT-7714 格式提取每条引用：
- 提取标题（从 cite 字符串中解析）
- 判断类型（`[J]` → article，`[M]` → book，`[EB/OL]` → website）
- 与 XML 已有条目去重（按标题精确匹配）

### A - 步骤2： 构建任务列表

读取 `参考文献列表.xml`，对每条引用判断状态：

```python
import xml.etree.ElementTree as ET
from pathlib import Path

def needs_content(entry):
    for tag in ["abstract", "related"]:
        el = entry.find(tag)
        if el is None or not (el.text or "").strip():
            return True
    return False
```

对每条引用：
- **无对应条目** → 任务类型 `new`
- **有条目但内容不完整** → 任务类型 `fill`
- **有完整条目** → 跳过

**PDF 匹配（article 类型）：**

```python
def match_pdf(title, pdf_dir="2_参考文献"):
    """取标题前3个有意义词（去停用词），在文件名中模糊匹配"""
    stopwords = {"的", "与", "和", "研究", "分析", "基于", "对", "在"}
    words = [w for w in title.replace("：", " ").replace(":", " ").split()
             if w not in stopwords][:3]
    for pdf in Path(pdf_dir).rglob("*.pdf"):
        if all(w in pdf.name for w in words):
            return str(pdf)
    return ""
```

- article 类型且找到匹配 PDF → `pdf_path` 填入，正常处理
- article 类型但**未找到 PDF** → `pdf_path` 为空，录入 XML 时 abstract/related 留空，加入待办「需要 PDF」
- website/book 类型 → 无需 PDF

**扫描孤立 PDF：**

```python
pdf_files = list(Path("2_参考文献").rglob("*.pdf"))
# 找出未被任何引用匹配到的 PDF
orphans = [p for p in pdf_files if not any_cite_matches(p)]
```

孤立 PDF（有文件但无对应 cite）→ **不录入 XML**，加入待办「需手动找引用」。

### A - 步骤3：并行处理

→ 见「通用并行处理」

---

## 模式 B：单条处理

仿照A进行模式步骤1-3的处理；

---

## 通用并行处理

**分配策略：至多启动 5 个 subagent，每个负责 ceil(N/5) 篇。**
超过 50 篇时分两轮，第一轮完成并写入 XML 后再启动第二轮。

**subagent prompt 模板：**

```
你是文献整理助手，处理以下 {N} 篇文献，逐篇处理后返回 JSON 数组。

研究课题：{RESEARCH_TOPIC}

待处理文献：
{
  "papers": [
    {
      "title": "标题",
      "type": "article|book|website",
      "cite": "引用格式",
      "pdf_path": "2_参考文献/xxx.pdf 或空字符串",
      "url": "网站URL或空字符串"
    }
  ]
}

对每篇文献：
1. 读取内容：
   - article 且有 pdf_path → Read 工具读取 PDF（前5页+最后2页）
   - article 且无 pdf_path → WebSearch 搜索标题找摘要（无 PDF 时尽力而为）
   - website → WebFetch 抓取 url
   - book → WebSearch 搜索书名（豆瓣优先，其次 Google Books）

2. 返回 JSON 数组（只返回 JSON，不要其他内容）：
[
  {
    "title": "原始标题（不修改）",
    "abstract": "5-6句中文摘要：背景→方法→发现→关联。面向在职MBA，禁用ASCII双引号，改用「」或《》",
    "related": "约90字，说明对研究课题的具体价值",
    "recommanded": "true 或 false",
    "path": "pdf_path 或 URL 或 空字符串",
    "doi": "DOI或空字符串",
    "todo": "空字符串，或：download_doi:https://doi.org/xxx | open_cnki:知网URL | not_found | web_failed | need_pdf"
  }
]

注意：
- 无法读取内容时，abstract 写「（内容无法获取，请手动补充）」，todo 填对应原因
- recommanded：这批中约1/3设为 true，优先理论框架类文献
```

**写入 XML：**

```python
def upsert_literature(xml_path, data, cite="", referred="true"):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    entry = None
    for lit in root.findall("literature"):
        t = lit.find("title")
        if t is not None and t.text == data["title"]:
            entry = lit
            break
    if entry is None:
        entry = ET.SubElement(root, "literature")

    def set_field(tag, value, overwrite=True):
        el = entry.find(tag)
        if el is None:
            el = ET.SubElement(entry, tag)
        if overwrite or not (el.text or "").strip():
            el.text = value or ""

    set_field("title",       data["title"],              overwrite=False)
    set_field("type",        data.get("type","article"), overwrite=False)
    set_field("path",        data.get("path",""),        overwrite=False)
    set_field("abstract",    data.get("abstract",""))
    set_field("related",     data.get("related",""))
    set_field("recommanded", data.get("recommanded",""))
    set_field("cite",        cite,                       overwrite=False)
    set_field("doi",         data.get("doi",""),         overwrite=False)
    set_field("referred",    referred,                   overwrite=False)

    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
```

---

## 步骤4：启动文献管理程序

启动：lsof -ti :8765 | xargs kill -9 2>/dev/null; python3 "${CLAUDE_SKILL_DIR}/scripts/literature_manager.py" --xml 参考文献列表.xml &

## 步骤5:更新信息

依据以下信息更新 `claude.md` 的目前进展章节 ：

[ ] 完成文献导入：`2_参考文献/格式化参考文献列表.md` 中的内容都存在于`2_参考文献/参考文献列表.xml`则 [✅]
[ ] 有足够文献：`2_参考文献/参考文献列表.xml` 中有 >= 20 篇文献则 [✅]
[ ] 有调研方案 `3_调研/参考文献列表.xml` 中有至少一篇方案，或`4_草稿`中已有调研数据则 [✅]
[ ] 完成调研分析 `3_调研/参考文献列表.xml` 中有至少一篇分析结论，或`4_草稿`中已有调研数据则 [✅]
[ ] 完成章节规划 `4_草稿`中已有草稿或正文 [✅]
[ ] 完成全部章节 `4_草稿`中最新一篇正文已完成全部章节 [✅]


## 完成，向用户汇报

```
## ths-paper-load 整理完成

共处理 N 篇，分 M 批完成。

### 已完成（N 篇）
| # | 标题 | 类型 | 摘要 | 推荐 |
|---|------|------|------|------|
| 1 | ... | article | ✅ | ⭐ |

### 📋 待办清单
- [ ] 【需要 PDF】《XXX》— article 类型，未找到匹配 PDF，摘要暂空；请下载后放入2_参考文献/，重新运行 /ths-paper-load
- [ ] 【需手动找引用】2_参考文献/xxx.pdf — 有 PDF 但未找到对应 cite，请在知网/Google Scholar 找到引用格式后贴给我
- [ ] 【去 DOI 下载】《XXX》— https://doi.org/xxx
- [ ] 【补充 cite】《XXX》— 无法自动获取引用格式，请在管理程序手动填入
- [ ] 【无法找到】《XXX》— 检索无结果
- [ ] 【网页无法访问】《XXX》— 请手动补充摘要

参考文献管理程序：http://localhost:8765

### 下一步建议
1....
2....
```

下一步建议规则（给出1-3项目）：
参考 `claude.md` 中的目前进展章节。
- 未完成文献导入：建议 /ths-paper-load 导入
- 没有足够文献：建议 /ths-paper-search 搜索文献
- 没有调研方案
  - 但`claude.md`的研究方法中有调查问卷：建议 /ths-questionaire 进行问卷设计；
  - 但`claude.md`的研究方法中没有调查问卷：建议直接讨论调研方法的设计；
- 未完成调研分析：建议 /ths-analyze 进行分析；
- 未完成章节规划：建议 /ths-write-now 进行章节规划；
- 未完成全部章节：建议 /ths-write-now 进行下一章撰写；
- 已完成全部章节：建议 /ths-review 进行 AI 审阅，或 ths-output 进行最终输出。

---

## Gotchas

- **预期控制**：每完成一步，告诉用户当前进度，如 "**任务进度(5/10)**"
- **XML 只由主 agent 写入**：subagent 只返回 JSON，不操作文件
- **cite 不覆盖**：`overwrite=False` 保护已有 cite
- **无 PDF 不阻塞**：article 无 PDF 时 subagent 仍尝试 WebSearch 找摘要，但 todo 标记 `need_pdf`
- **孤立 PDF 不录入**：有文件无 cite → 只加待办，不写 XML
- **摘要禁用 ASCII 双引号**：用「」或《》
- **模式 B 去重**：按标题精确匹配，已在 XML 的跳过
- **recommanded 全局校正**：主 agent 收集所有结果后，确保整体约 1/3 为 true

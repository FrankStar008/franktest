---
name: ths-paper-search
description: |
  MBA毕业论文文献检索助手。支持两种模式：
  ① 直接检索：基于论文选题，拆分3个检索方向，并行在知网检索15篇（中8+英7）+互联网检索5篇；
  ② 补充检索：基于指定方向，在知网检索5篇（中3+英2）+互联网检索2篇。
  检索完成后输出结构化汇报和待办清单。
  触发词：「找文献」「帮我检索」「从零检索」「补充这个方向的文献」「搜一下XXX方向的文献」
---

# ths-paper-search

## 第零步：判断模式与输出

| 模式 | 触发条件 | 目标 |
|------|---------|------|
| **直接检索** | 用户提供论文选题 / claude.md 中有选题 | 知网 15 篇（中8+英7）+ 互联网 5 篇 |
| **补充检索** | 用户指定补充方向 | 知网 5 篇（中3+英2）+ 互联网 2 篇 |

输出任务信息：

```
=================
任务：**搜索文献（ths-paper-search）**

目标：Agent 自动检索知网，找到与本次论文相关的中英文文献（请提登录知网），需要手动下载。

大约需要时间：N 分钟；
=================
```

如果直接检索：20-30分钟
如果补充检索：10-20分钟；

---


## 第二步：拆分检索方向（直接检索专用）

读取 `claude.md` 中的论文选题。

基于论文选题，拆出 **3 个检索方向**，每个方向是一个具体的子问题或维度：

**示例**（选题：「AI时代险企营销员留存管理」）：
1. 保险营销员流失的影响因素与留存机制
2. AI工具对保险业务员工作方式的影响
3. 知识工作者绩效考核与激励设计

补充检索模式直接使用用户指定的方向，无需拆分。

---

## 第三步：并行启动子 Agent

### 直接检索模式：并行启动 4 个子 Agent

**同时**启动以下 4 个子 Agent（不等待，并行执行）：
- Agent A1、A2、A3：分别负责一个知网检索方向
- Agent B：互联网检索

**每个知网方向 Agent（A1 / A2 / A3）的 Prompt 模板：**

```
你是一个知网文献检索助手，只负责一个检索方向。

检索方向：{方向N} —— 目标：中文 2-3 篇 + 外文 2-3 篇

必须加载 web-access skill 并遵循其指引。CDP proxy 检查：
  node "/Users/tongshen/.claude/skills/web-access/scripts/check-deps.mjs"

知网 CDP 操作规范（严格遵守）：
1. 打开知网：curl -s "http://localhost:3456/new?url=https://kns.cnki.net/kns8s/"
2. 关键词生成：针对本方向拆出 2 组关键词，格式 `词A * ( 词B + 词C )`（运算符前后必须有空格，只用2个维度，3维度会返回0结果）
3. 填入并搜索（先填值，再点按钮，Enter 键不可靠）：
   - 填值：eval → `var i=document.querySelector("#txt_search"); i.value="关键词"; ["input","change"].forEach(e=>i.dispatchEvent(new Event(e,{bubbles:true}))); "ok"`
   - 触发：eval → `document.querySelector(".search-btn")?.click(); "ok"`，sleep 3
4. 切中文标签：eval → `Array.from(document.querySelectorAll("*")).find(e=>e.childNodes.length===1&&e.textContent.trim()==="中文")?.click()`，sleep 2
5. 提取结果：eval → `var r=[]; document.querySelectorAll("a.fz14").forEach(a=>{ if(!a.href.includes("kcms"))return; var row=a.closest("tr,.content-item,li"); var meta=row?.innerText?.split("\n").map(s=>s.trim()).filter(s=>s).slice(0,4).join(" | ")||""; r.push({title:a.textContent.trim(),href:a.href,meta}); }); JSON.stringify(r.slice(0,20))`
6. **【必须执行，不得跳过】** 切外文标签：eval → `document.querySelector("a.en")?.click(); "ok"`，sleep 3，直接提取（同步骤5，不需要重新搜索，外文是同一搜索结果的语种过滤）。中文已达标不是跳过此步的理由。
7. 对本方向重复两组关键词，合并去重（中文+外文一起合并）
8. 相关性评分（1-5），中文和外文**分别**取 ≥3 分的论文
9. **【不要开 tab】** 只返回 URL 列表，不用 curl 打开详情页。
10. 将结果写入以下文献的最后：
    - `2_参考文献/格式化参考文献列表.md`（追加，文件不存在则创建），每篇三行格式：
      ```
      标题：{标题}
      链接：{知网URL}
      cite：
      ```
      每篇之间空一行

返回格式：
每篇论文列出：标题、来源（期刊/学位论文）、年份、语言（中/英）、知网URL
```

**3 个知网 Agent 全部完成后**，主流程读取三个方向文件，去重合并。

### 补充检索模式：并行启动 2 个子 Agent

**同时**启动以下 2 个子 Agent：
- Agent A：知网检索（单方向）
- Agent B：互联网检索

**补充检索知网 Agent Prompt 模板：**

```
你是一个知网文献检索助手。

检索目标：对以下方向在知网检索，目标：中文 3 篇 + 外文 2 篇：
  {方向}

必须加载 web-access skill 并遵循其指引。CDP proxy 检查：
  node "/Users/tongshen/.claude/skills/web-access/scripts/check-deps.mjs"

知网 CDP 操作规范（严格遵守）：
1. 打开知网：curl -s "http://localhost:3456/new?url=https://kns.cnki.net/kns8s/"
2. 关键词生成：针对本方向拆出 2 组关键词，格式 `词A * ( 词B + 词C )`（运算符前后必须有空格，只用2个维度，3维度会返回0结果）
3. 填入并搜索（先填值，再点按钮，Enter 键不可靠）：
   - 填值：eval → `var i=document.querySelector("#txt_search"); i.value="关键词"; ["input","change"].forEach(e=>i.dispatchEvent(new Event(e,{bubbles:true}))); "ok"`
   - 触发：eval → `document.querySelector(".search-btn")?.click(); "ok"`，sleep 3
4. 切中文标签：eval → `Array.from(document.querySelectorAll("*")).find(e=>e.childNodes.length===1&&e.textContent.trim()==="中文")？.click()`，sleep 2
5. 提取结果：eval → `var r=[]; document.querySelectorAll("a.fz14").forEach(a=>{ if(!a.href.includes("kcms"))return; var row=a.closest("tr,.content-item,li"); var meta=row?.innerText?.split("\n").map(s=>s.trim()).filter(s=>s).slice(0,4).join(" | ")||""; r.push({title:a.textContent.trim(),href:a.href,meta}); }); JSON.stringify(r.slice(0,20))`
6. **【必须执行，不得跳过】** 切外文标签：eval → `document.querySelector("a.en")?.click(); "ok"`，sleep 3，直接提取
7. 重复两组关键词，合并去重
8. 相关性评分（1-5），中文和外文**分别**取 ≥3 分的论文
9. **【不要开 tab】** 不用 curl 打开详情页
10. 将结果写入：
    - `2_参考文献/格式化参考文献列表.md`（追加，文件不存在则创建），每篇三行格式：
      ```
      标题：{标题}
      链接：{知网URL}
      cite：
      ```
      每篇之间空一行

返回格式：
每篇论文列出：标题、来源（期刊/学位论文）、年份、语言（中/英）、知网URL
```

完成后，将本文件

### 子 Agent B：互联网检索

Prompt 模板：
```
你是一个互联网权威资料检索助手。目标是找到可在论文中引用的权威网页资料，**不是学术论文**（论文由知网检索覆盖，不要重复）。

检索目标：
[直接检索] 对以下3个方向各找 1-2 条权威网页资料，总计 5 条：
  1. {方向1}
  2. {方向2}
  3. {方向3}

[补充检索] 对以下方向找 2 条权威网页资料：
  {方向}

使用 WebSearch + WebFetch 获取内容。

**优先寻找以下类型（按优先级）：**
1. 政府/监管机构官网数据（如国家统计局、人社部、各行业主管部门）
2. 权威行业协会报告（如中国人力资源和社会保障研究院、麦肯锡、德勤发布的行业报告）
3. 主流财经媒体深度调查报道（第一财经、财新、哈佛商业评论中文版等）
4. 企业官方发布的白皮书或年度调研报告

**明确排除：**
- 学术论文、知网/万方文献（已由知网 Agent 覆盖）
- 个人博客、知乎问答、百度百科
- 营销软文、无署名来源的文章

对每条找到的资料：
1. 获取完整标题、发布机构、发布年份、URL
2. 生成 GBT-7714 格式引用：
   - 报告/网页：发布机构. 标题[EB/OL]. (年份)[引用日期]. URL.
3. 将内容追加写入 `2_参考文献/格式化参考文献列表.md`（文件不存在则创建），每篇三行格式：
   ```
   标题：{标题}
   链接：{URL}
   cite：{GBT-7714引用}
   ```
   每篇之间空一行

返回格式：
每篇文档列出：标题、来源机构、年份、URL、GBT引用
```

---

## 第四步：更新信息

依据以下信息更新 `claude.md` 的目前进展章节 ：

[ ] 完成文献导入：`2_参考文献/格式化参考文献列表.md` 中的内容都存在于`2_参考文献/参考文献列表.xml`则 [✅]
[ ] 有足够文献：`2_参考文献/参考文献列表.xml` 中有 >= 20 篇文献则 [✅]
[ ] 有调研方案 `3_调研/参考文献列表.xml` 中有至少一篇方案，或`4_草稿`中已有调研数据则 [✅]
[ ] 完成调研分析 `3_调研/参考文献列表.xml` 中有至少一篇分析结论，或`4_草稿`中已有调研数据则 [✅]
[ ] 完成章节规划 `4_草稿`中已有草稿或正文 [✅]
[ ] 完成全部章节 `4_草稿`中最新一篇正文已完成全部章节 [✅]


## 完成，向用户汇报

两个子 Agent 完成后，输出以下汇报：

```
## 检索完成

### 知网文献（共 X 篇）
| # | 标题 | 来源 | 年份 | 语言 |
|---|------|------|------|------|
| 1 | ... | ... | ... | 中/英 |

### 互联网文档（共 X 篇）
| # | 标题 | 来源 | 年份 | URL |
|---|------|------|------|-----|
| 1 | ... | ... | ... | ... |

所有文献已写入 `2_参考文献/格式化参考文献列表.md`。

---

### 📋 待办清单

**知网文献（需手动操作）：**
- [ ] 打开 `2_参考文献/格式化参考文献列表.md`，依次点击每条知网链接（`链接：` 行）
- [ ] 中文文献：点击「PDF下载」→ 保存到 `2_参考文献/` 目录；点击引用按钮（引号图标）→ 选 GBT 格式 → 填入对应条目的 `cite：` 行
- [ ] 英文文献：点击”全部来源”下的链接，在目标网站下载 PDF 到 `2_参考文献/` 目录；找到 cite，获取 GBT 格式引用并填入对应条目的 `cite：` 行

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
- **关键词维度**：只用 2 个维度 `词A * ( 词B + 词C )`，3 维度必然返回 0 结果
- **空格格式**：`*` `+` `(` `)` 前后必须有空格
- **搜索触发**：必须用 `.search-btn` click，Enter 键事件实测不生效
- **外文标签**：用 `document.querySelector("a.en")?.click()`（DOM 实测：`<a class="en" data-val="Foreign">`），文本匹配不可靠；切换后直接提取，不需要重新输入英文关键词搜索
- **中文标签**：`a.cn` 不存在，只能用文本匹配 `Array.from(document.querySelectorAll("*")).find(e=>e.childNodes.length===1&&e.textContent.trim()==="中文")?.click()`
- 切换后等 2-3s 再提取
- **结果 selector**：`a.fz14`，只保留 href 含 `kcms` 的
- **IP 登录**：用户 Chrome 已有机构 IP 登录态，无需额外处理
- **参考文献目录**：写入前检查 `2_参考文献/` 是否存在，不存在则创建
# Summer School Radar 技术说明

这是一个面向科研季节性学校与短期课程的开源 radar。它关注 summer school、winter school、spring/autumn school、training school、field school、doctoral school、research school、short/advanced course，**不收普通会议 workshop**;主题聚焦 water、hydrology、climate、geoscience、remote sensing 和 scientific machine learning。

项目目标不是全网乱爬，也不是做一个万能 agent。目标是维护可信来源列表，定期扫描，结构化抽取 deadline、funding、fee、duration、mode、eligibility 等高风险字段，严格筛选，并发布透明的静态报告和网页。

## 当前已经实现

- 固定可信来源扫描
- 从来源页继续跟进二级候选链接
- 基于规则的结构化抽取
- 硬筛条件和 near-match 分离
- 可解释排序和去重
- Markdown 报告生成
- GitHub Pages 静态网页生成
- 浏览器端筛选器
- `data/opportunities.yml` 人工确认机会库
- `site/curated.json` 和 `site/candidates.json`
- `site/sources.html` 和 `site/sources.json`
- JSON seen-state tracking
- GitHub Actions 每日自动扫描和部署
- GitHub issue 投稿模板
- Cloudflare Web Analytics / GoatCounter 可选统计脚本
- deadline 的 `Add to calendar` `.ics` 下载链接
- pytest 测试覆盖核心流程

## 核心工作流

```text
config/sources.yaml
        |
        v
collect.py  ->  抓取固定来源页面
        |
        v
parse.py    ->  发现候选机会链接
        |
        v
collect.py  ->  抓取候选详情页
        |
        v
extract.py  ->  抽取 Candidate 结构化记录
        |
        v
filter.py   ->  应用硬筛条件
        |
        v
rank.py     ->  打分和去重
        |
        +--> report.py  -> reports/YYYY-MM-DD.md
        |
        +--> site.py    -> site/index.html + JSON 数据
        |
        +--> storage.py -> data/seen.json
```

## 关键文件

- `src/research_school_radar/cli.py`：命令入口
- `collect.py`：抓取来源页和详情页
- `parse.py`：识别候选链接，跳过 PDF、图片、Office 文件和被屏蔽域名
- `extract.py`：规则抽取 title、location、dates、deadline、funding、mode 等字段
- `filter.py`：硬筛，失败项进入 `failed_hard_conditions`
- `rank.py`：解释性打分和去重
- `report.py`：生成 Markdown 报告
- `site.py`：生成静态网站、筛选器、JSON、日历链接和 analytics 脚本
- `storage.py`：JSON seen-state file

## 配置文件

- `config/profile.yaml`：主题、硬筛条件、资金可及性阈值、参考汇率和地区优先级
- `config/sources.yaml`：可信来源列表，可设置 `enabled: false` 和 `blocked_link_domains`
- `config/queries.yaml`：可选 controlled discovery 查询
- `config/site.yaml`：可选 analytics 配置
- `data/opportunities.yml`：人工确认的高可信机会库

## Sources & Coverage 页面

项目会从 `config/sources.yaml` 生成：

- `site/sources.html`
- `site/sources.json`

这个页面列出所有 configured sources，包括 enabled 和 disabled 的来源、layer、region、source_type、keywords、notes，以及 blocked linked domains。它的目的不是展示“我们爬了全网”，而是明确项目维护的是 trusted source registry。

公开机会表格不再展示 `region priority` 和 `failed hard condition` 这类内部字段。它们仍保留在 `site/candidates.json` 中供维护者检查和调试。Title 本身直接链接到官方页面。

## Fully Qualified 条件

机会必须同时满足：

- deadline 未过期或明确开放
- duration 至少 8 天
- funding 明确存在，例如 scholarship、travel grant、tuition waiver、stipend、accommodation support；或者可确认的总费用按参考汇率换算后不超过 400 EUR
- in-person 或 substantially on-site
- 主题与配置文件中的研究方向相关

任何字段不确定时，默认不进入 fully qualified，而是进入 near-match。失败条件保留在 `site/candidates.json` 中，不再占用公开表格列。

项目收录 `training school`，因为很多科研组织用这个名称表示与 summer school 类似的短期密集训练。普通 conference workshop 整体被排除（它们很少是有资助的多日学校）；其余硬条件再作用于保留下来的学校与课程类型。

## 资金可及性规则

资金硬条件满足以下任意一种即可：

- 页面明确提供 participant funding；
- 能明确抽取并换算的总费用不超过 `maximum_unfunded_fee_eur`，默认是 400 EUR。

`extract.py` 会识别常见货币代码和符号、免费参加以及费用区间。遇到费用区间时使用最高金额，避免只按早鸟价误判。外币通过 `config/profile.yaml` 中的 `financial_access.approximate_currency_to_eur` 固定参考汇率换算。

固定汇率让 GitHub Actions 保持免费、确定性运行，不需要汇率 API key。它不是实时市场汇率，并且采用偏保守数值。币种或金额无法可靠识别时，项目仍进入 near-match，不会自动视为低费用。

## Doctoral School 的口径

项目保留 `doctoral school` 这个词，是因为很多欧洲或研究网络会把短期科研训练叫 doctoral school、PhD school、graduate training school 或 doctoral training school。

但项目不收：

- PhD admissions
- PhD positions
- full-time doctoral degree programmes
- ordinary graduate school enrollment

也就是说，我们只收短期科研训练机会，不收博士招生或博士职位。

## Curated Workflow

自动扫描只负责发现 candidate。可信发布层来自人工确认：

```text
scanner output
    -> reports/YYYY-MM-DD.md
    -> site/candidates.json
    -> maintainer review
    -> data/opportunities.yml
    -> Curated Opportunities section
```

外部用户可以通过 GitHub issue template 投稿。维护者检查官方链接、deadline、funding、duration、mode、eligibility 后，再把记录加入 `data/opportunities.yml`。

## GitHub Actions 和 Pages

每日规则扫描由维护者电脑上的 `scripts/scan_and_publish.ps1` 运行，使用住宅网络抓取官网并把 `site/` 发布到 `gh-pages`。

`.github/workflows/ai_scan.yml` 提供每周一次或手动触发的 AI 辅助扫描。它从 GitHub repository secrets 读取 `DEEPSEEK_API_KEY`，运行 `bge-m3`、受限补页和 DeepSeek 证据抽取，再把经过证据验证、并重新执行原有硬筛选后的结果直接写入首页三张表，发布到同一个 `gh-pages` 分支。项目不再生成单独的公开 AI Review 页面；`site/ai_extractions.json` 继续保留证据和验证警告。`BRAVE_SEARCH_API_KEY` 和 `HF_TOKEN` 是可选 secret；缺少 Brave key 时仍会进行官网内部补页。

## Analytics

GitHub Pages 本身没有长期、公开的 analytics dashboard。项目通过 `config/site.yaml` 支持可选前端统计：

```yaml
analytics:
  provider: none
  cloudflare_token: ""
  goatcounter_code: ""
```

可选：

- `cloudflare`：Cloudflare Web Analytics
- `goatcounter`：GoatCounter

默认不注入任何 tracking script。

## 当前限制

- 抽取仍然是规则驱动，复杂页面可能抽错字段
- 日期和 deadline 只覆盖常见英文格式
- funding detection 可能把 acknowledgements 当成 participant support
- 固定参考汇率需要偶尔人工维护，不是实时汇率
- 一些来源页是宽泛 index page，near-match 会偏弱
- `data/opportunities.yml` 仍然需要手动编辑
- 没有 RSS feed
- 没有自动开 review issue
- 没有字段级 confidence score
- 没有 source-specific parser adapter

## 下一步建议

优先级最高的改进：

1. 给 deadline、funding、duration、mode 加 field-level confidence 和 evidence snippets
2. 给 EGU、ICIMOD、ELLIS、IHE Delft、CUAHSI 写 source-specific parsers
3. 生成 RSS feed
4. 加 `review promote` 命令，把 `site/candidates.json` 的候选项提升到 `data/opportunities.yml`
5. 对高分新候选自动开 GitHub issue，标签为 `needs-review`
6. 增加 weekly digest
7. 增加历史 report archive 页面

## 设计原则

- precision 比 recall 更重要
- near-match 不能伪装成 fully qualified
- deadline 和 funding 必须尽量保留证据
- 简单可靠的 scanner 优于不可解释的 autonomous browser
- LLM 可以以后辅助抽取，但不应控制搜索和浏览
- 真正的价值来自 curated quality，而不是链接数量

# Summa 技术说明

Summa 是一个面向多学科科研训练机会的开源扫描器。它覆盖 summer school、winter school、spring/autumn school、training school、field school、doctoral school、research school、short/advanced course 等短期科研训练项目，不收普通会议 workshop、博士招生、博士职位或完整学位项目。

项目目标不是全网乱爬，也不是让模型自主浏览网页。Summa 维护一组可信来源，定期扫描官方页面，抽取 deadline、funding、fee、duration、mode、eligibility 等高风险字段，经过硬筛选后发布可审计的静态网页、Markdown 报告、JSON 数据和 RSS feed。

## 三分钟启动

```powershell
git clone https://github.com/lione12138/summer-school-radar.git
cd summer-school-radar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m research_school_radar.cli scan --offline-sample
```

然后查看：

- `reports/YYYY-MM-DD.md`：Markdown 报告
- `site/index.html`：静态网页
- `site/candidates.json`：schema v2 候选快照；`opportunities` 保存首页展示副本，`scanner_opportunities` 隔离保存 RSS 使用的确定性扫描记录
- `site/curated.json`：人工维护的高可信记录
- `site/feed.xml`：RSS feed

真实来源扫描：

```powershell
python -m research_school_radar.cli scan
```

普通 HTTP 页面会缓存到已忽略的 `data/http_cache/`。缓存保存页面正文、最终 URL、`ETag` 和 `Last-Modified`。后续扫描会发送 `If-None-Match` / `If-Modified-Since`，源站返回 `304 Not Modified` 时直接复用本地正文。需要强制刷新时使用：

```powershell
python -m research_school_radar.cli scan --refresh-http-cache
```

## 当前能力

- 多学科可信来源扫描
- 来源页二级候选链接跟进
- 直接 JSON/API collector，例如 IHE Delft、ELLIS；是否启用统一由 `config/sources.yaml` 的 `collector` 字段控制
- 规则抽取 title、location、dates、deadline、funding、mode、fee、eligibility 等字段
- 高风险字段 evidence 保留和抽取置信度
- 硬筛选：fully qualified 与 near-match 分离
- 可解释排序与去重
- Markdown 报告生成
- 静态网页生成，支持浏览器端筛选
- `site/candidates.json`、`site/curated.json`、`site/sources.json`
- `site/sources.html` 来源覆盖页面
- `site/feed.xml` RSS 2.0 feed
- sitemap、robots、JSON-LD、canary、watermark 等 SEO/发布辅助文件
- `data/opportunities.yml` 人工确认机会库
- `data/seen.json` seen-state tracking
- 可选 Cloudflare Web Analytics / GoatCounter
- 可选 semantic ranking：`BAAI/bge-m3`
- 可选 DeepSeek 证据抽取与中文展示文案生成
- 条件 HTTP 缓存、14 天 stale-if-error 回退、综合来源覆盖门槛和快照数量保持校验
- 本机采集、快照提交与 GitHub Actions 单写入者发布相分离
- 模块化测试文件：`test_extract.py`、`test_site.py`、`test_rank.py`、`test_collect.py`、`test_report.py`、`test_review.py`、`test_storage.py` 等

## 核心工作流

```text
config/sources.yaml
        |
        v
collect.py + http_cache.py  -> 抓取固定来源页和候选详情页
        |
        v
parse.py                  -> 发现候选机会链接
        |
        v
extract.py                -> 规则抽取 Candidate 结构化记录
        |
        v
filter.py                 -> 应用硬筛条件
        |
        v
rank.py                   -> 打分和去重
        |
        +--> report.py    -> reports/YYYY-MM-DD.md
        |
        +--> site.py      -> site/index.html + JSON/RSS/SEO 文件
        |
        +--> storage.py   -> data/seen.json
```

可选 AI 分支：

```text
pages
    -> semantic chunks
    -> evidence snippets
    -> DeepSeek extraction
    -> evidence-ID validation
    -> homepage candidate copies + sidecar JSON
```

AI 分支不会覆盖扫描器原始 `Candidate` 对象。它只会在生成首页时对候选副本填补缺失字段，然后重新运行同一套硬筛选和排序。Markdown 报告、RSS、seen-state 和 curated 数据仍以规则候选为准。

结构化 collector 生成的记录使用 `Candidate.identity_key` 作为稳定身份。去重时它优先于 URL、标题和日期相似度，并贯穿 candidate JSON、seen-state、RSS GUID 和详情页文件名。

`config/sources.yaml` 同时控制普通页面来源与直接 collector。只有启用且声明了 `collector` 的来源才会调用对应的 `api_sources.py` 收集器，不存在另一套隐藏的硬编码启用列表。

## 关键文件

- `src/research_school_radar/cli.py`：命令入口
- `src/research_school_radar/collect.py`：抓取来源页和详情页，普通请求使用条件 HTTP 缓存
- `src/research_school_radar/http_cache.py`：保存正文、最终 URL、`ETag`、`Last-Modified`；请求异常、HTTP 429 或 5xx 时可回退到不超过 14 天的缓存，404 和过旧缓存不会回退
- `src/research_school_radar/parse.py`：识别候选链接，跳过 PDF、图片、Office 文件和被屏蔽域名
- `src/research_school_radar/extract.py`：规则抽取结构化字段
- `src/research_school_radar/filter.py`：硬筛，失败项进入 `failed_hard_conditions`
- `src/research_school_radar/rank.py`：解释性打分和去重；优先使用采集器提供的稳定身份，在事实合并后重新硬筛和评分
- `src/research_school_radar/report.py`：生成 Markdown 报告
- `src/research_school_radar/site.py`：协调静态网站生成
- `src/research_school_radar/site_styles.py`：CSS 常量
- `src/research_school_radar/site_i18n.py`：中英文词典、前端语言切换脚本、翻译缓存辅助
- `src/research_school_radar/site_seo.py`：sitemap、robots、JSON-LD、canary、watermark
- `src/research_school_radar/site_feed.py`：RSS feed 渲染
- `src/research_school_radar/urls.py`：外链进入 HTML、JSON-LD 或 RSS 前的安全校验
- `src/research_school_radar/atomic_io.py`：原子替换生成文本，并重试 Windows 短暂文件锁
- `src/research_school_radar/storage.py`：维护 `data/seen.json`
- `src/research_school_radar/semantic.py`：可选语义 chunk sidecar
- `src/research_school_radar/evidence_snippets.py`：为 LLM 提供短证据片段
- `src/research_school_radar/ai_cache.py`：可选 AI 分支缓存
- `src/research_school_radar/llm_client.py`、`llm_extract.py`、`llm_validate.py`：DeepSeek 调用、抽取和验证
- `src/research_school_radar/ai_healthcheck.py`：检查 DeepSeek 配置是否可用
- `src/research_school_radar/scan_health.py`：拒绝未尝试任何来源的真实扫描，要求普通页面与直连 collector 合计至少 70% 成功，并生成扫描 manifest
- `src/research_school_radar/snapshot_validation.py`：要求 schema v2 的展示/扫描记录均非空，并在旧快照规模足够大时阻止扫描记录无解释地跌到 35% 以下
- `src/research_school_radar/programme_sessions.py`：统一生成网页、报告和 RSS 使用的多时段日期及分时段截止日期文案
- `src/research_school_radar/ai_pipeline.py`：集中管理 semantic 排序、DeepSeek 配置、补页编排与 AI sidecar 生成，使 `cli.py` 保持为入口协调器
- `src/research_school_radar/ai_output_validation.py`：AI 快照替换上一个可用快照前，检查 semantic、DeepSeek 抽取与构建时中文翻译是否可用
- `src/research_school_radar/ai_evaluate.py`：生成真人标注 CSV 模板

## 配置文件

- `config/profile.yaml`：主题、硬筛条件、资金可及性阈值、参考汇率、地区优先级和排除项目类型
- `config/sources.yaml`：可信来源列表，可设置 `enabled: false`、`render: true`、`blocked_link_domains` 和结构化直连收集器 `collector`
- `config/queries.yaml`：可选 controlled discovery 查询
- `config/site.yaml`：可选 analytics 配置
- `config/ai.yaml`：semantic ranking、DeepSeek 抽取、资源上限和 AI cache 配置
- `data/opportunities.yml`：人工确认的高可信机会库

## Fully Qualified 条件

机会必须同时满足：

- 申请开放，或 deadline 未过期
- duration 至少 8 天
- 明确存在 scholarship、travel grant、tuition waiver、stipend、accommodation support 等 participant funding；或者可确认的总费用按参考汇率换算后不超过 400 EUR
- in-person 或 substantially on-site，不是 online-only
- 主题与 `config/profile.yaml` 中的研究方向相关

如果 deadline 无法抽取，但项目开始日期已经过去，也会视为过期。字段不确定时默认不进入 fully qualified，而是进入 near-match。失败条件保留在 `site/candidates.json` 中，供维护者检查，不占用公开表格列。

## 多学科范围

Summa 现在不是单一 water/climate 列表。默认 profile 面向 MSc、PhD、postdoc 和 early-career research training，覆盖：

- environmental & earth science
- computing & data science
- social sciences
- humanities methods
- 以及配置文件中维护的交叉方向

真正的领域边界由 `config/profile.yaml` 的 `preferred_topics` 决定。扩大或收窄领域时，优先修改 profile 和 trusted source registry，而不是让模型全网搜索。

## 资金可及性规则

资金硬条件满足以下任意一种即可：

- 页面明确提供 participant funding；
- 能明确抽取并换算的总费用不超过 `maximum_unfunded_fee_eur`，默认是 400 EUR。

`extract.py` 会识别常见货币代码和符号、免费参加以及费用区间。遇到费用区间时使用最高金额，避免只按早鸟价误判。外币通过 `config/profile.yaml` 中的 `financial_access.approximate_currency_to_eur` 固定参考汇率换算。

固定汇率让扫描保持免费、确定性运行，不需要汇率 API key。它不是实时市场汇率，并且采用偏保守数值。币种或金额无法可靠识别时，项目仍进入 near-match，不会自动视为低费用。

## Doctoral School 的口径

项目保留 `doctoral school` 这个词，是因为很多欧洲或研究网络会把短期科研训练叫 doctoral school、PhD school、graduate training school 或 doctoral training school。

但项目不收：

- PhD admissions
- PhD positions
- full-time doctoral degree programmes
- ordinary graduate school enrollment

也就是说，Summa 只收短期科研训练机会，不收博士招生或博士职位。

## DeepSeek / AI 边界

默认扫描不依赖任何 LLM，也不需要 API key。可选 AI 分支做两件事：

1. 用 `BAAI/bge-m3` 对已抓取页面做语义排序，挑出更可能包含机会信息的 chunk；
2. 把短编号证据片段发送给 DeepSeek，生成结构化草稿和中文展示文案。

当前代码只支持 DeepSeek 作为远程 LLM provider。配置方式：

```powershell
$env:LLM_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "sk-..."
python -m research_school_radar.ai_healthcheck --provider deepseek
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction
```

DeepSeek 收到的是筛选后的短证据片段，不是完整网页，也没有浏览器控制权。模型输出必须引用 evidence IDs；`llm_validate.py` 会检查 ID 是否存在、字段是否有对应上下文、日期/费用/closed 语言是否有明显冲突。带 validation warning 的字段不会用于首页 merge。

生产自动化还有第二层构建级门槛：
`python -m research_school_radar.ai_output_validation --site-dir site` 必须确认存在可用 semantic chunks 和至少一条通过证据校验的 DeepSeek 抽取，AI 运行才可以替换 last-known-good 快照。

AI 结果保存在：

- `site/ai_extractions.json`
- `reports/YYYY-MM-DD.ai.json`

它们是 advisory sidecar，不是 curated database。进入 curated 层仍然需要维护者查看官方页面，并编辑 `data/opportunities.yml` 或 `data/overrides.yml`。

## Sources & Coverage 页面

项目会从 `config/sources.yaml` 生成：

- `site/sources.html`
- `site/sources.json`

这个页面列出所有 configured sources，包括 enabled 和 disabled 来源、layer、region、source_type、keywords、notes，以及 blocked linked domains。它的目的不是展示“我们爬了全网”，而是明确项目维护的是 trusted source registry。

公开机会表格不展示 `region priority` 和 `failed hard condition` 这类内部字段。它们仍保留在 `site/candidates.json` 中供维护者检查和调试。扫描结果标题链接到站内详情页；只有通过 HTTP(S) 安全校验的外链才会显示官网操作按钮。

## Curated Workflow

自动扫描只负责发现 candidate。可信发布层来自人工确认：

```text
scanner output
    -> reports/YYYY-MM-DD.md
    -> site/candidates.json
    -> maintainer review
    -> data/opportunities.yml
    -> public curated layer
```

外部用户可以通过 GitHub issue template 投稿。维护者检查官方链接、deadline、funding、duration、mode、eligibility 后，再把记录加入 `data/opportunities.yml`。

## 发布工作流

采集与发布已经拆开。维护者电脑每天运行 `scripts/scan_and_publish.ps1`，利用住宅网络访问 GitHub-hosted runner 容易受限的官方站点。周一、周三、周五执行 semantic + DeepSeek 辅助完整扫描；只有严格 DeepSeek healthcheck、`scan_health.py` 的综合来源覆盖门槛、`ai_output_validation.py` 以及 `snapshot_validation.py` 的 schema/数量保持校验都通过，才会替换 last-known-good 快照。

其他日期执行：

```powershell
python -m research_school_radar.cli refresh-status --candidates-json data/latest_candidates.json
```

这个过程只重新计算 deadline/open/closed 等日期状态，不访问来源页面，也不覆盖来源扫描快照；GitHub Pages 的每日任务会执行同样的无抓取重建并发布。三份版本化输入快照是：

- `data/latest_candidates.json`
- `data/latest_sources.json`
- `data/latest_scan_manifest.json`

完整本机扫描的同一次提交还可以包含更新后的 `seen.json`、review queue 和带日期的 Markdown 报告，用于保留扫描历史与审计记录；它们不是另一条 Pages 发布通道。

本机任务不写 `gh-pages`。`.github/workflows/ai_scan.yml` 是 `gh-pages` 的唯一写入者，并使用单一 publisher concurrency group 防止并发发布。它每天从已提交快照执行无抓取的 `refresh-status`，再把生成的 `site/` 发布到 Pages。

云端 AI 扫描只支持手动触发。手动选择 `ai` mode 时，workflow 才读取 GitHub repository secrets 中的 `DEEPSEEK_API_KEY`，运行 `bge-m3`、受限补页和 DeepSeek 证据抽取，通过 `ai_output_validation.py` 与 `snapshot_validation.py` 后保存快照，并由同一个单写入者流程发布。

可选 secret：

- `BRAVE_SEARCH_API_KEY`：启用受控的同域搜索补页
- `HF_TOKEN`：提高 Hugging Face 模型下载额度

secret 不会写入生成文件或提交。

## 静态网站输出

网站生成器会写入：

- `site/index.html`
- `site/candidates.json`
- `site/curated.json`
- `site/sources.html`
- `site/sources.json`
- `site/feed.xml`
- `site/sitemap.xml`
- `site/robots.txt`
- `site/.nojekyll`

网页支持浏览器端筛选：

- 关键词搜索
- status
- topic
- financial access
- deadline status

已知 deadline 的行会生成 `Add to calendar` `.ics` 下载链接，方便导入 Apple Calendar、Google Calendar、Outlook 等日历。

## 可选 Headless Rendering

大多数来源直接返回可解析 HTML，用 `requests` 即可。少数站点需要客户端渲染，可在 `config/sources.yaml` 中设置：

```yaml
render: true
```

安装方式：

```powershell
pip install -e ".[render]"
python -m playwright install chromium
```

如果没有安装 Playwright，`render: true` 来源会自动回退到普通请求，默认工作流保持轻量。AI 辅助 GitHub workflow 可以安装并缓存浏览器，让需要渲染的来源在 CI 中工作。

## 当前限制

- 抽取仍以规则为主，复杂页面可能抽错字段
- 日期和 deadline 覆盖常见英文格式，但 month-only、跨版次、混合日期仍可能不确定
- funding detection 可能被少见措辞误导，尤其是 acknowledgement、membership fellowship 或外部资助说明
- 固定参考汇率需要偶尔人工维护，不是实时汇率
- listing、calendar、navigation、landing page 会被严格过滤，少数真实机会可能等详情页发布后才被发现
- `data/opportunities.yml` 仍然需要手动编辑，目前没有 curator UI
- promising candidate 还不会自动开 PR/issue
- JavaScript 筛选没有持久化用户偏好
- DeepSeek 分支仍需人工抽检官方页面，不能直接视为事实认证

## 下一步建议

优先级最高的改进：

1. 给 deadline、funding、duration、mode 加更细的 field-level confidence 和 evidence 展示
2. 继续补高价值来源的 source-specific parser 或 direct collector
3. 增加 `review promote` 命令，把 `site/candidates.json` 候选提升到 `data/opportunities.yml`
4. 对高分新候选自动开 GitHub issue 或 PR，标签为 `needs-review`
5. 增加 weekly digest、Telegram 或 email 订阅
6. 增加历史 report archive 页面
7. 增加自定义域名和 Cloudflare Analytics 配置说明
8. 给 README 增加截图或示例报告段落

## 设计原则

- precision 比 recall 更重要
- near-match 不能伪装成 fully qualified
- deadline 和 funding 必须尽量保留证据
- 简单可靠的 scanner 优于不可解释的 autonomous browser
- LLM 只能辅助抽取和翻译，不应控制搜索和浏览
- curated quality 比链接数量更重要

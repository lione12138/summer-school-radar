# 来源修复核查：2026-09-21

本报告逐项复核 9 月 18 日快照中失败的 16 个来源。已修复与外部限制分别记录；未通过降低 TLS 校验或绕过访问验证改变状态。

| 来源 | 当前结论 | 处理 |
|---|---|---|
| DAAD Short Courses | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| GESIS Summer School | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| GESIS Fall Seminar in Computational Social Science | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| GESIS Spring Seminar | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| EITM Institute | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| Lamont-Doherty | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| Climate Change AI | 已修复本机依赖 | 已安装匹配版本的 Chromium headless shell；官网重放成功。 |
| CERN Academic Training | 已修复本机依赖 | 浏览器安装后官网重放成功。 |
| AGU | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| ESSLLI | 仍受官网访问限制 | 修复浏览器依赖后仍返回验证页；现在明确记为失败。 |
| LASER Software Engineering School | 停用过时来源 | 改为基金会官方地址，官网明确学校暂停，保留停用条目。 |
| SOLAS | 重试恢复 | 无需改代码；本次直接抓取成功。 |
| Argonne ATPESC | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| IHR History | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| Alan Turing Institute | 仍受官网访问限制 | 当前返回 HTTP 403，保留失败状态，需要官网或网络访问条件恢复。 |
| Stazione Zoologica | 证书链校验失败 | 保留 TLS 验证与失败状态，需修复服务端证书链或受信任的本机 CA 配置。 |

LASER 暂停声明：[LASER Foundation](https://www.laser-foundation.org/)。

## 已确认的候选漏抓修复

- IAHS：官方域名限定的 Academy 年份链接发现；保留 EUR 650 一般费用以及 EUR 350 的适用人群。
- ECMWF：完整 Indico 培训目录；确定性与语义词表均加入 training course；课程链接优先于通用付费说明链接。
- Eurac：注册主页/项目/申请/费用页关联，按同届项目合并并保存字段来源；完整日期为 2027-02-01 至 2027-02-12。
- Essex：两条同名 source 合并为一条，申请页继续明确采集。

## 指标和自动运行

- 不把零候选自动判为异常或无项目；分别记录抓取健康、去重前抽取量、去重后 scanner 记录和连续零结果次数。
- 9/21 本机任务返回 0xC000013A，且没有该次扫描日志；只能确认被中断，无法确定中断发起者。
- 已保留安装任务原触发时间，添加隐藏窗口及每 15 分钟、最多 3 次失败重试。
- 修复后完整扫描在 logs/recall-repair 下隔离运行，只有全部生产检查通过才可以替换正式快照。

## 最终验证与本地交付

2026-09-21 完整扫描：157 个启用来源，145 成功、12 失败；143 条原始候选，127 条 scanner 记录，132 条展示快照记录。语义/DeepSeek 输出、快照 schema/保留率、站点完整性三项检查全部通过，本地三份正式快照与 site 已更新；旧快照备份位于 logs/recall-repair/previous-snapshots。未提交或推送 Git，因此线上尚未部署。

生成站点包含四条资助/低费推荐：Al-Nour、Eurac、IAHS Academy、ECMWF 卫星数据同化。ALPS 申请页已采集，按当前 EUR 700 费用进入自费目录。IAHS 最终审查通过，Eurac 无重复条目。

471 项 Python 测试、Ruff、wheel 资源与隔离渲染检查通过。来源页中英文及 360/390/768/1440px 交互检查通过。完整 UI 脚本存在既有首屏断言失败：390px 下首条结果 y=745.58px，高于脚本阈值 740px；旧 site 与新 site 的测量相同。


## 2026-09-22：12 个访问失败来源逐项复核

以下是本机无缓存定向复测，不是新一轮全量扫描。原始响应记录在本地 `logs/access-audit-2026-09-22.json`。403 只能确认此环境下访问失败，不能据此认定官网没有项目，也不能证明所有网络都失败。

| 来源 | 复核与替代入口 | 处理结论 |
| --- | --- | --- |
| DAAD Short Courses | 原入口和 www2.daad.de 夏季课程入口均返回 administrative rules 403 | 解析适配器无法处理缺失正文；暂保留失败。语言课程奖学金不是研究学校的等价替代。 |
| GESIS Summer School | gesis.org 与 training.gesis.org 目录均为 Cloudflare 403 | 未来适合按目录课程 ID 建 collector，分别保留各课程日期；当前网络层阻塞，暂不编写无法实测的 collector。 |
| GESIS Fall Seminar | 同上；目录实际按课程、线上/线下、售罄状态分别组织 | 与 Summer 共用未来目录 collector；不能把整个系列日期作为连续课程。 |
| GESIS Spring Seminar | 同上；Moodle 学习资料目录不是报名目录 | 不使用课程资料页冒充开放申请来源。 |
| EITM Institute | 官网主页仍为 Cloudflare 403；找到的官方项目资料为 2025，Princeton 入口为更早届次 | 未确认可持续的当前报名替代入口，保留失败。 |
| Lamont-Doherty | professional-development 路径也为 Cloudflare 403 | 不用本科实习列表替代研究学校目录；保留失败。 |
| AGU | 原站 Cloudflare 403；AGU Connect 水文学学生资源页可访问，但培训链接指向 CUAHSI | 可访问的静态资源页不等价于 AGU 当前培训目录，暂不替换。 |
| ESSLLI | 官方 Tartu 2027 主办页 HTTP 200 | 已改注册入口并增加域名/路径限定适配器。识别 2027-08-02 至 08-13、Tartu 线下、春季才开始报名；讲师 proposal 截止和费用报销不作为学生申请条件。年度主办链接需要跟随下一届更新。 |
| Argonne ATPESC | 项目官网及 /attend 均 Cloudflare 403；ALCF 官方 2026 招生新闻 HTTP 200 | 可作历史佐证，但 2026 届已结束；新闻仍指向受限官网，未将旧新闻替换成长期入口。 |
| IHR History | 研究培训路径和 SAS 上级培训入口仍为 Cloudflare 403 | 旧 archive 页面不能代表当前报名，暂保留失败。 |
| Alan Turing Institute | /courses 仍为 Cloudflare 403 | 未找到等价且可访问的当前研究学校目录；中学生项目不能替代。 |
| Stazione Zoologica | 默认证书库报证书链错误；系统信任库在保持证书/域名校验时 HTTP 200 | 已加入显式 tls_trust: system，且改到官方 Advanced Courses & Summer schools 目录。课程页只提取 Joomla 正文，排除导航里其他课程日期。 |

官方可访问证据：[ESSLLI Tartu 2027](https://digits.ut.ee/esslli-2027/)、[SZN 培训目录](https://szn.it/it/formazione/advanced-courses-summer-schools)、[ATPESC 2026 官方新闻](https://www.alcf.anl.gov/news/applications-now-open-2026-argonne-training-program-extreme-scale-computing)、[AGU 学生资源](https://connect.agu.org/hydrology/hidden/students/student-resources)。

SZN 实测发现 MiNaPOLL 2027；正文适配后正确提取 2027-02-23 至 02-26（4 天）、申请截止 2026-12-10。它是否展示仍由既有时长等 hard filters 决定，不因恢复抓取而自动推荐。系统信任库行为依赖运行平台，本次已在维护者 Windows 环境验证；没有关闭证书验证、全局 SSL 修改或失败后不安全重试。

本轮明确恢复 2/12 个来源；其余 10 个仍缺乏已验证的等价当前入口。没有人工修改历史 manifest 的成功计数，也没有覆盖上一轮完整扫描快照。新状态须经下一次完整生产扫描及门禁后发布。

本轮验证：477 项 pytest 全部通过，Ruff 通过；ESSLLI 与 SZN 真实入口及有界关联页面复测无抓取错误，重放结果保存在本地 `logs/access-repair-replay-2026-09-22.json`。尚未提交、推送或部署。

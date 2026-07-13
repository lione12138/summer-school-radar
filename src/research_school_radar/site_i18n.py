from __future__ import annotations

# Runs in <head> before first paint, so the saved theme and language apply with
# no flash. Plain string (real JS braces), interpolated as a value.
_BOOT_SCRIPT = (
    "<script>(function(){try{"
    "var t=localStorage.getItem('summa-theme');"
    "if(t!=='light'&&t!=='dark'){t=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';}"
    "document.documentElement.setAttribute('data-theme',t);"
    "var l=localStorage.getItem('summa-lang');"
    "if(l!=='zh'&&l!=='en'){l=((navigator.language||'en').toLowerCase().indexOf('zh')===0)?'zh':'en';}"
    "document.documentElement.setAttribute('lang',l);"
    "}catch(e){}})();</script>"
)


# Applies translations to [data-i18n] elements and wires the two toggle buttons.
# Runs at the end of <body>. Plain string (real JS braces).
_UI_SCRIPT = """
  <script>
  (function(){
    var I18N = {
      "nav.opportunities": {en:"Opportunities", zh:"机会"},
      "nav.how": {en:"How it works", zh:"工作原理"},
      "nav.about": {en:"About", zh:"关于"},
      "nav.sources": {en:"Sources", zh:"来源"},
      "hero.kicker": {en:"Updated daily \\u00B7 Free & open source", zh:"每天更新 \\u00B7 免费开源"},
      "hero.title": {en:"Find research training worth applying for", zh:"寻找真正值得申请的科研训练机会"},
      "hero.subtitle": {en:"Funded and low-fee opportunities from trusted academic sources. Every deadline and funding claim stays traceable to the official page.", zh:"从可信学术来源汇总有资助或低费用的科研训练机会。每条截止日期和资助信息都可追溯到官网。"},
      "hero.disclaimer": {en:"Use this as a starting point, not the only source. Information is collected from official university and organization pages, but automated extraction can still be wrong. Always verify deadlines, fees, funding, and eligibility on the official page. High-quality official sources that cannot be collected automatically are listed in Collection Notes. Wishing everyone admission to a programme they are excited about.", zh:"请把这里当作基础信息入口，而不是唯一信息来源。本站信息来自各大组织和学校官网，但自动收集和解析仍可能因为技术问题出错；申请前请务必到官网核对截止日期、费用、资助和资格要求。少数质量很高但暂时无法自动收集的官网已列在采集说明里。祝大家都能录到心仪的项目。"},
      "cta.email": {en:"Get email alerts", zh:"邮件订阅"},
      "cta.explore": {en:"Explore opportunities", zh:"浏览开放项目"},
      "cta.qualification": {en:"How qualification works", zh:"了解筛选标准"},
      "subscribe.title": {en:"Stay updated", zh:"订阅最新项目"},
      "subscribe.lead": {en:"Get an email when new funded schools open — no spam, unsubscribe anytime.", zh:"有新的资助项目开放时接收邮件提醒；无垃圾邮件，可随时退订。"},
      "subscribe.email.placeholder": {en:"you@example.com", zh:"你的邮箱"},
      "subscribe.email.label": {en:"Email address", zh:"邮箱地址"},
      "subscribe.submit": {en:"Get email alerts", zh:"订阅邮件提醒"},
      "opportunities.title": {en:"Open opportunities", zh:"开放申请的项目"},
      "action.details": {en:"View details", zh:"查看详情"},
      "action.official": {en:"Official page", zh:"官方网站"},
      "action.official.open": {en:"Open official page", zh:"打开官方网站"},
      "action.official.programme": {en:"Open official programme page ↗", zh:"打开项目官网 ↗"},
      "calendar.add": {en:"Add to calendar", zh:"添加到日历"},
      "badge.new": {en:"NEW", zh:"新增"},
      "meta.updated": {en:"Updated", zh:"更新"},
      "meta.fixed": {en:"Fixed-source scan", zh:"固定来源扫描"},
      "meta.free": {en:"No paid search API", zh:"无需付费搜索 API"},
      "meta.sources": {en:"Sources & Coverage", zh:"来源与覆盖"},
      "stat.qualified": {en:"Fully qualified", zh:"完全符合"},
      "stat.near": {en:"High quality", zh:"高质量"},
      "stat.sources": {en:"Trusted sources", zh:"可信来源"},
      "stat.updated": {en:"Last updated", zh:"最近更新"},
      "filter.search": {en:"Search", zh:"搜索"},
      "filter.search.placeholder": {en:"Title, organizer, location", zh:"标题、主办方、地点"},
      "filter.status": {en:"Status", zh:"状态"},
      "filter.topic": {en:"Topic", zh:"主题"},
      "filter.funding": {en:"Financial Access", zh:"费用/资助"},
      "filter.deadline": {en:"Deadline", zh:"截止日期"},
      "filter.fresh": {en:"Freshness", zh:"新近程度"},
      "filter.all": {en:"All", zh:"全部"},
      "filter.status.qualified": {en:"Fully qualified", zh:"完全符合"},
      "filter.status.high": {en:"High quality", zh:"高质量"},
      "filter.status.found": {en:"Found", zh:"待核实"},
      "filter.status.curated": {en:"Curated", zh:"人工精选"},
      "filter.funding.explicit": {en:"Explicit funding", zh:"明确提供资助"},
      "filter.funding.low": {en:"Low / no fee", zh:"低费用或免费"},
      "filter.funding.unresolved": {en:"Unresolved / high fee", zh:"费用未确认或较高"},
      "filter.deadline.open": {en:"Open", zh:"开放申请"},
      "filter.deadline.uncertain": {en:"Uncertain", zh:"待确认"},
      "filter.deadline.closed": {en:"Closed", zh:"已截止"},
      "filter.new.today": {en:"New today", zh:"今日新增"},
      "table.title": {en:"Title", zh:"项目名称"},
      "table.organizer": {en:"Organizer", zh:"主办方"},
      "table.location": {en:"Location", zh:"地点"},
      "table.duration": {en:"Duration", zh:"时长"},
      "table.deadline": {en:"Deadline", zh:"截止日期"},
      "table.funding": {en:"Funding / Fee", zh:"资助 / 费用"},
      "table.topic": {en:"Topic", zh:"主题"},
      "table.notes": {en:"Notes", zh:"备注"},
      "table.actions": {en:"Actions", zh:"操作"},
      "tier.qualified": {en:"Fully Qualified Opportunities", zh:"完全符合的项目"},
      "tier.high": {en:"High-Quality Opportunities", zh:"高质量项目"},
      "tier.found": {en:"Found Opportunities", zh:"待核实项目"},
      "tier.curated": {en:"Curated Opportunities", zh:"人工精选项目"},
      "tier.high.lead": {en:"Relevant funded or low-fee opportunities that still need official-page verification.", zh:"有资助或费用较低、但仍需到官网核实的相关项目。"},
      "tier.found.lead": {en:"Relevant leads with unresolved evidence.", zh:"证据尚未完整核实的相关线索。"},
      "tier.curated.lead": {en:"Maintainer-reviewed records with source evidence.", zh:"由维护者审核并保留来源证据的项目。"},
      "detail.back": {en:"← Back to opportunities", zh:"← 返回项目列表"},
      "detail.overview": {en:"Overview", zh:"项目概览"},
      "detail.eligibility": {en:"Who should apply", zh:"适合谁申请"},
      "detail.why": {en:"Why this status", zh:"为何获得此状态"},
      "detail.source": {en:"Official source", zh:"官方来源"},
      "detail.source.original": {en:"Original source evidence is retained below for verification.", zh:"以下保留官方原文证据，便于核对。"},
      "detail.source.unavailable": {en:"No safe official URL is available for this record.", zh:"这条记录暂时没有可安全访问的官方网址。"},
      "detail.snapshot": {en:"Application snapshot", zh:"申请信息速览"},
      "detail.funding": {en:"Funding / fee", zh:"资助 / 费用"},
      "detail.deadline": {en:"Application deadline", zh:"申请截止日期"},
      "detail.verify": {en:"Always verify eligibility, fees, funding, and dates on the official page.", zh:"申请前请务必在官方网站核对资格、费用、资助和日期。"},
      "sources.title": {en:"Sources & Coverage", zh:"来源与覆盖范围"},
      "sources.lead": {en:"The radar scans a trusted source registry rather than crawling the open web. This page lists the configured sources, including disabled sources kept for transparency.", zh:"雷达只扫描人工维护的可信来源，不进行开放网络泛爬。本页列出所有配置来源，包括为保持透明而保留的停用来源。"},
      "sources.back": {en:"Back to radar", zh:"返回雷达"},
      "sources.json": {en:"Source JSON", zh:"来源 JSON"},
      "sources.configured": {en:"Configured Sources", zh:"已配置来源"},
      "sources.direct": {en:"Sources to Check Directly", zh:"需要直接查看的来源"},
      "sources.direct.lead": {en:"We cannot fetch these automatically yet. Please open them directly to look for opportunities.", zh:"这些来源目前无法稳定自动抓取，请直接打开官网查看机会。"},
      "sources.source": {en:"Source", zh:"来源"},
      "sources.status": {en:"Status", zh:"状态"},
      "sources.health": {en:"Scan health", zh:"扫描健康状态"},
      "sources.layer": {en:"Layer", zh:"层级"},
      "sources.region": {en:"Region", zh:"地区"},
      "sources.type": {en:"Type", zh:"类型"},
      "sources.keywords": {en:"Keywords", zh:"关键词"},
      "sources.notes": {en:"Notes (original registry text)", zh:"备注（保留原始配置文本）"},
      "sources.reason": {en:"Why it is not fetched automatically", zh:"无法自动抓取的原因"},
      "sources.enabled": {en:"enabled", zh:"已启用"},
      "sources.disabled": {en:"disabled", zh:"已停用"},
      "notes.title": {en:"Collection Notes", zh:"采集说明"},
      "empty.title": {en:"Nothing open right now — but the radar is watching", zh:"目前没有开放项目，但雷达仍在监测"},
      "empty.link": {en:"See what we track", zh:"查看监测来源"},
      "how.title": {en:"How it works", zh:"工作原理"},
      "how.lead": {en:"A transparent pipeline you can audit — not a black box.", zh:"一条可以审计的透明流程，不是黑箱。"},
      "how.1.title": {en:"Scan trusted sources", zh:"扫描可信来源"},
      "how.1.body": {en:"Every Monday, Wednesday, and Friday, the radar fetches a fixed registry of vetted academic sources: scientific societies, research institutes, and established schools.", zh:"每周一、周三和周五从固定的、人工筛选过的学术来源列表抓取信息，包括学会、研究机构和成熟暑校。"},
      "how.2.title": {en:"Extract evidence", zh:"提取证据"},
      "how.2.body": {en:"Rule-based extraction pulls out dates, deadline, funding, fee, location, and mode, with source text kept for verification.", zh:"规则提取日期、截止时间、资助、费用、地点和形式，并保留来源文本方便核验。"},
      "how.3.title": {en:"Apply strict filters", zh:"应用严格筛选"},
      "how.3.body": {en:"Only funded or low-fee, in-person opportunities with an open deadline in covered domains are treated as qualified.", zh:"只有有资助或低费用、线下、仍在报名且属于覆盖领域的项目才会被标为完全符合。"},
      "how.4.title": {en:"Publish daily", zh:"每日发布"},
      "how.4.body": {en:"The results are committed and published to this static site for quick public review.", zh:"结果会提交并发布到这个静态网站，方便公开查看。"},
      "about.title": {en:"About & methodology", zh:"关于与方法"},
      "about.lead": {en:"What this is, what it covers, and where the line is drawn.", zh:"说明它是什么、覆盖什么，以及边界在哪里。"},
      "about.what.title": {en:"What it is", zh:"它是什么"},
      "about.what.body": {en:"Summa is an open-source, fixed-source scanner with rule-based extraction and transparent per-field evidence. It is not a fully automatic all-web crawler.", zh:"Summa 是一个开源的固定来源扫描器，使用规则提取，并为每个字段保留证据。它不是全网自动爬虫。"},
      "about.domains.title": {en:"Domains covered", zh:"覆盖领域"},
      "about.domains.body": {en:"It covers environmental and earth science, computing and data science, and selected social-science and humanities methods fields. The same quality filters apply across fields.", zh:"覆盖环境与地球科学、计算与数据科学，以及部分社会科学和人文学科方法领域。所有领域使用同一套质量筛选标准。"},
      "about.qualifies.title": {en:"What qualifies", zh:"什么算符合"},
      "about.q1": {en:"Funded, or low / no fee — not an expensive paid course.", zh:"有资助，或低费用/免费，而不是昂贵付费课程。"},
      "about.q2": {en:"In-person — virtual-only events are set aside.", zh:"线下参与；纯线上活动会被排除。"},
      "about.q3": {en:"An application deadline that is still open.", zh:"申请截止日期仍未过去。"},
      "about.q4": {en:"A real research school, training school, field school, or short course — not a conference or a full degree programme.", zh:"是真正的研究暑校、训练营、田野学校或短课程，而不是会议或完整学位项目。"},
      "about.q5": {en:"On-domain in the topics above.", zh:"主题属于上面覆盖的学科范围。"},
      "about.evidence.title": {en:"Evidence and honesty", zh:"证据与透明度"},
      "about.evidence.body": {en:"Every extracted field carries source evidence where available. Near-matches are shown separately and never counted as qualified.", zh:"每个可提取字段都会尽量保留来源证据。近似匹配会单独展示，不会被当作完全符合。"},
      "faq.title": {en:"Frequently asked", zh:"常见问题"},
      "faq.lead": {en:"Quick answers about scope, updates, and contributing.", zh:"关于范围、更新和参与方式的简短回答。"},
      "faq.1.q": {en:"Is it free?", zh:"它免费吗？"},
      "faq.1.a": {en:"Yes — entirely free and open source. There is no paywall, no account, and no paid search API in the default pipeline.", zh:"免费，而且开源。默认流程没有付费墙、不需要账号，也不依赖付费搜索 API。"},
      "faq.2.q": {en:"How often is it updated?", zh:"多久更新一次？"},
      "faq.2.a": {en:"The site is rebuilt daily to refresh deadline status. Source pages are fetched every Monday, Wednesday, and Friday.", zh:"网站每天重建以刷新截止日期状态；来源页面在每周一、周三和周五重新抓取。"},
      "faq.3.q": {en:"Why are some events only near-matches?", zh:"为什么有些项目只是近似匹配？"},
      "faq.3.a": {en:"They are relevant but fail at least one strict rule, such as uncertain deadline, high fee, unresolved fee, or virtual-only format.", zh:"它们相关，但至少有一条严格规则没通过，例如截止日期不确定、费用过高、费用未确认，或只有线上形式。"},
      "faq.4.q": {en:"How do you avoid spam and low-quality listings?", zh:"怎么避免低质量信息？"},
      "faq.4.a": {en:"The radar only reads a curated registry of trusted academic sources. It does not crawl the open web.", zh:"它只读取人工维护的可信学术来源列表，不做开放网络泛爬。"},
      "faq.5.q": {en:"Can I suggest a source?", zh:"我可以建议来源吗？"},
      "faq.5.a": {en:"Yes. Open an issue on GitHub with the source and its events page, and it can be added to the registry.", zh:"可以。在 GitHub issue 里提交来源和活动页面，维护者可以把它加入来源列表。"},
      "foot.opportunities": {en:"Opportunities", zh:"机会"},
      "foot.sources": {en:"Sources & coverage", zh:"来源与覆盖"},
      "foot.how": {en:"How it works", zh:"工作原理"},
      "foot.about": {en:"About & methodology", zh:"关于与方法"},
      "foot.faq": {en:"FAQ", zh:"常见问题"},
      "foot.suggest": {en:"Suggest a source", zh:"建议来源"},
      "foot.issue": {en:"Report an issue", zh:"报告问题"},
      "foot.star": {en:"Star on GitHub", zh:"在 GitHub 收藏"},
      "foot.explore": {en:"Explore", zh:"浏览"},
      "foot.project": {en:"Project", zh:"项目"},
      "foot.contribute": {en:"Contribute", zh:"参与"},
      "foot.blurb": {en:"A free, open-source scanner for funded research summer schools, winter schools, and training schools across many academic fields. Updated daily.", zh:"一个免费的开源扫描器，追踪多个学科中有资助的暑校、冬校和训练营项目。每天更新。"},
      "foot.legal": {en:"Near-matches are not treated as qualified opportunities. Built and maintained openly on GitHub.", zh:"近似匹配不会被当作完全符合的机会。项目在 GitHub 上公开维护。"}
    };
    function txt(el, lang){
      var d=I18N[el.getAttribute('data-i18n')];
      if(!d||d[lang]==null) return;
      if(el.hasAttribute('data-i18n-html')) el.innerHTML=d[lang]; else el.textContent=d[lang];
    }
    function attr(el, lang){
      var key=el.getAttribute('data-i18n-placeholder');
      var d=I18N[key];
      if(d&&d[lang]!=null) el.setAttribute('placeholder', d[lang]);
      var ariaKey=el.getAttribute('data-i18n-aria-label');
      var aria=I18N[ariaKey];
      if(aria&&aria[lang]!=null) el.setAttribute('aria-label', aria[lang]);
    }
    function applyLang(lang){
      document.documentElement.setAttribute('lang', lang);
      var els=document.querySelectorAll('[data-i18n]'); for(var i=0;i<els.length;i++) txt(els[i], lang);
      var attrs=document.querySelectorAll('[data-i18n-placeholder],[data-i18n-aria-label]'); for(var j=0;j<attrs.length;j++) attr(attrs[j], lang);
      var labels=document.querySelectorAll('[data-label-en][data-label-zh]');
      for(var k=0;k<labels.length;k++) labels[k].textContent=labels[k].getAttribute('data-label-'+lang);
      var titleKey='pageTitle'+(lang==='zh'?'Zh':'En');
      if(document.body&&document.body.dataset[titleKey]) document.title=document.body.dataset[titleKey];
      var b=document.getElementById('lang-toggle'); if(b) b.textContent = (lang==='zh')?'EN':'中';
      try{localStorage.setItem('summa-lang', lang);}catch(e){}
      try{document.dispatchEvent(new CustomEvent('summa:languagechange',{detail:{lang:lang}}));}catch(e){}
    }
    function applyTheme(t){
      document.documentElement.setAttribute('data-theme', t);
      var b=document.getElementById('theme-toggle'); if(b) b.textContent = (t==='dark')?'\\u2600':'\\u263E';
      try{localStorage.setItem('summa-theme', t);}catch(e){}
    }
    applyLang(document.documentElement.getAttribute('lang')||'en');
    applyTheme(document.documentElement.getAttribute('data-theme')||'light');
    var lb=document.getElementById('lang-toggle'); if(lb) lb.addEventListener('click', function(){ applyLang(document.documentElement.getAttribute('lang')==='zh'?'en':'zh'); });
    var tb=document.getElementById('theme-toggle'); if(tb) tb.addEventListener('click', function(){ applyTheme(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark'); });
  })();
  </script>"""


from __future__ import annotations


def how_it_works_section() -> str:
    steps = [
        ("1", "Scan trusted sources", "Every Monday, Wednesday, and Friday, the radar fetches a fixed registry of vetted academic sources: scientific societies, research institutes, and established schools.", "how.1.title", "how.1.body"),
        ("2", "Extract evidence", "Rule-based extraction pulls out dates, deadline, funding, fee, location, and mode, with source text kept for verification.", "how.2.title", "how.2.body"),
        ("3", "Apply strict filters", "Only funded or low-fee, in-person opportunities with an open deadline in covered domains are treated as qualified.", "how.3.title", "how.3.body"),
        ("4", "Publish daily", "The results are committed and published to this static site for quick public review.", "how.4.title", "how.4.body"),
    ]
    cards = "".join(
        f'<div class="step"><span class="n">{n}</span><h3 data-i18n="{title_key}">{title}</h3>'
        f'<p data-i18n="{body_key}">{body}</p></div>'
        for n, title, body, title_key, body_key in steps
    )
    return f"""
    <section id="how" class="anchor">
      <div class="section-head">
        <h2 data-i18n="how.title">How it works</h2>
        <p class="lead" data-i18n="how.lead">A transparent pipeline you can audit — not a black box.</p>
      </div>
      <div class="steps">{cards}</div>
    </section>"""


def about_section() -> str:
    return """
    <section id="about" class="anchor">
      <div class="section-head">
        <h2 data-i18n="about.title">About &amp; methodology</h2>
        <p class="lead" data-i18n="about.lead">What this is, what it covers, and where the line is drawn.</p>
      </div>
      <div class="panel">
        <h3 data-i18n="about.what.title">What it is</h3>
        <p data-i18n="about.what.body">Summa is an open-source, fixed-source scanner with rule-based extraction and transparent per-field evidence. It is not a fully automatic all-web crawler.</p>
        <h3 data-i18n="about.domains.title">Domains covered</h3>
        <p data-i18n="about.domains.body">It covers environmental and earth science, computing and data science, and selected social-science and humanities methods fields. The same quality filters apply across fields.</p>
        <h3 data-i18n="about.qualifies.title">What qualifies</h3>
        <ul class="criteria">
          <li data-i18n="about.q1">Funded, or low / no fee — not an expensive paid course.</li>
          <li data-i18n="about.q2">In-person — virtual-only events are set aside.</li>
          <li data-i18n="about.q3">An application deadline that is still open.</li>
          <li data-i18n="about.q4">A real research school, training school, field school, or short course — not a conference or a full degree programme.</li>
          <li data-i18n="about.q5">On-domain in the topics above.</li>
        </ul>
        <h3 data-i18n="about.evidence.title">Evidence and honesty</h3>
        <p data-i18n="about.evidence.body">Every extracted field carries source evidence where available. Near-matches are shown separately and never counted as qualified.</p>
      </div>
    </section>"""


def faq_section() -> str:
    qa = [
        ("faq.1.q", "faq.1.a", "Is it free?", "Yes — entirely free and open source. There is no paywall, no account, and no paid search API in the default pipeline."),
        ("faq.2.q", "faq.2.a", "How often is it updated?", "The site is rebuilt daily to refresh deadline status. Source pages are fetched every Monday, Wednesday, and Friday."),
        ("faq.3.q", "faq.3.a", "Why are some events only near-matches?", "They are relevant but fail at least one strict rule, such as uncertain deadline, high fee, unresolved fee, or virtual-only format."),
        ("faq.4.q", "faq.4.a", "How do you avoid spam and low-quality listings?", "The radar only reads a curated registry of trusted academic sources. It does not crawl the open web."),
        ("faq.5.q", "faq.5.a", "Can I suggest a source?", "Yes. Open an issue on GitHub with the source and its events page, and it can be added to the registry."),
    ]
    items = "".join(
        f'<details><summary data-i18n="{q_key}">{question}</summary><p data-i18n="{a_key}">{answer}</p></details>'
        for q_key, a_key, question, answer in qa
    )
    return f"""
    <section id="faq" class="anchor">
      <div class="section-head">
        <h2 data-i18n="faq.title">Frequently asked</h2>
        <p class="lead" data-i18n="faq.lead">Quick answers about scope, updates, and contributing.</p>
      </div>
      <div class="faq">{items}</div>
    </section>"""

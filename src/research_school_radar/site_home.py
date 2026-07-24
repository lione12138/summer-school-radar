from __future__ import annotations

from .site_assets import render_template


def how_it_works_section() -> str:
    steps = [
        {
            "number": "1",
            "title": "Scan trusted sources",
            "body": "Every Monday, Wednesday, and Friday, the radar fetches a fixed registry of vetted academic sources: scientific societies, research institutes, and established schools.",
            "title_key": "how.1.title",
            "body_key": "how.1.body",
        },
        {
            "number": "2",
            "title": "Extract evidence",
            "body": "Rule-based extraction pulls out dates, deadline, funding, fee, location, and mode, with source text kept for verification.",
            "title_key": "how.2.title",
            "body_key": "how.2.body",
        },
        {
            "number": "3",
            "title": "Apply strict filters",
            "body": "Only funded or low-fee, in-person opportunities with an open deadline in covered domains are treated as qualified.",
            "title_key": "how.3.title",
            "body_key": "how.3.body",
        },
        {
            "number": "4",
            "title": "Publish daily",
            "body": "The results are committed and published to this static site for quick public review.",
            "title_key": "how.4.title",
            "body_key": "how.4.body",
        },
    ]
    return render_template("home/how.html", steps=steps)


def about_section() -> str:
    return render_template("home/about.html")


def faq_section() -> str:
    items = [
        {
            "question_key": "faq.1.q",
            "answer_key": "faq.1.a",
            "question": "Is it free?",
            "answer": "Yes — entirely free and open source. There is no paywall, no account, and no paid search API in the default pipeline.",
        },
        {
            "question_key": "faq.2.q",
            "answer_key": "faq.2.a",
            "question": "How often is it updated?",
            "answer": "The site is rebuilt daily to refresh deadline status. Source pages are fetched every Monday, Wednesday, and Friday.",
        },
        {
            "question_key": "faq.3.q",
            "answer_key": "faq.3.a",
            "question": "Why are some events only near-matches?",
            "answer": "They are relevant but fail at least one strict rule, such as uncertain deadline, high fee, unresolved fee, or virtual-only format.",
        },
        {
            "question_key": "faq.4.q",
            "answer_key": "faq.4.a",
            "question": "How do you avoid spam and low-quality listings?",
            "answer": "The radar only reads a curated registry of trusted academic sources. It does not crawl the open web.",
        },
        {
            "question_key": "faq.5.q",
            "answer_key": "faq.5.a",
            "question": "Can I suggest a source?",
            "answer": "Yes. Open an issue on GitHub with the source and its events page, and it can be added to the registry.",
        },
    ]
    return render_template("home/faq.html", items=items)

from __future__ import annotations

from research_school_radar.localization_audit import localization_issues


def test_localization_audit_rejects_unmarked_interface_text() -> None:
    html = '<html><body><h2>New English heading</h2><script>var I18N = {};</script></body></html>'
    assert localization_issues(html) == ["unlocalized_ui_text:h2:New English heading"]


def test_localization_audit_accepts_dictionary_and_bilingual_content() -> None:
    html = """
    <html><body>
      <h2 data-i18n="page.title">Page title</h2>
      <a class="button"><span class="lang-en">View details</span><span class="lang-zh">查看详情</span></a>
      <script>var I18N = {
        "page.title": {en:"Page title", zh:"页面标题"}
      };</script>
    </body></html>
    """
    assert localization_issues(html) == []

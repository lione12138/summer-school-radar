from research_school_radar.scan_quality import attach_extraction_health
from research_school_radar.page_validation import require_content_page
import pytest


def test_zero_candidates_are_unverified_not_failed():
    records = [{'name': 'Empty', 'status': 'healthy'}, {'name': 'Failed', 'status': 'failed'}]
    quality = {'per_source': {name: {'extracted_records': 0, 'scanner_records': 0} for name in ['Empty','Failed']}}
    previous = {'mode':'full', 'source_health':[{'name':'Empty','consecutive_empty_scans':4}]}
    attach_extraction_health(records, quality, previous)
    assert records[0]['fetch_health'] == 'healthy'
    assert records[0]['extraction_health'] == 'no_records'
    assert records[0]['consecutive_empty_scans'] == 5
    assert records[1]['extraction_health'] == 'unavailable'


def test_deduplicated_candidate_still_counts_as_extracted():
    records = [{'name':'Source', 'status':'healthy'}]
    quality = {'per_source': {'Source': {'extracted_records':1, 'scanner_records':0}}}
    attach_extraction_health(records, quality, None)
    assert records[0]['extraction_health'] == 'records_found'


def test_challenge_page_does_not_count_as_fetch_success():
    with pytest.raises(ValueError, match='access challenge'):
        require_content_page('<title>Just a moment...</title><p>Verifying you are human</p>')
    require_content_page('<title>Winter School</title><p>Registration opens soon.</p>')

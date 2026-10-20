import sys
sys.path.insert(0, r'D:\Program Files\Downloads\Thesis\traba-hero\backend')

from app.services.lm_client import _parse_custom as lm_parse_custom
from app.services.scanner.verification_flow import _read_verify_output

# Test with a sample custom format
sample = """VALID: true
ANOMALY: Asks applicants to pay a processing fee | The posting asks for 500 peso fee before starting | high
END ANOMALIES
ATTRIBUTES:
COMPANY: Acme Corporation
LOCATION: Quezon City
END ATTRIBUTES
SEARCH QUERIES:
QUERY: Acme Corporation Philippines
END SEARCH QUERIES
EMPLOYER NAME: Acme Corporation
POSTING ANALYSIS:
The posting offers a data entry role with pay per task. Applicants must complete forms to earn.
END POSTING ANALYSIS
JOB SUMMARY:
Daily data entry work from home, 500 pesos per task completed.
END JOB SUMMARY"""

# Parse with lm_client _parse_custom
parsed = lm_parse_custom(sample)
print('lm_parse_custom result:')
print('  valid:', parsed.get('valid'))
print('  anomalies:', parsed.get('anomalies'))
print('  attributes:', parsed.get('attributes'))
print('  search_queries:', parsed.get('search_queries'))

# Now try _read_verify_output
print()
print('Testing _read_verify_output:')
try:
    result = _read_verify_output(sample)
    items, report, rec, used_json, evidence, risk_level, risk_score, verdict_reason, assessments = result
    print('  Items:', [(i.label, i.status, i.explanation) for i in items])
    print('  Report:', report[:80])
    print('  Recommendation:', rec)
    print('  Evidence:', evidence)
    print('  Risk level:', risk_level)
    print('  Risk score:', risk_score)
    print('  Verdict reason:', verdict_reason)
    print('  Assessments:', assessments)
    print('  Used JSON:', used_json)
except Exception as e:
    print('  Error:', e)
    import traceback
    traceback.print_exc()
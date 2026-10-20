import sys
sys.path.insert(0, r'D:\Program Files\Downloads\Thesis\traba-hero\backend')

from app.services.lm_client import _parse_custom as lm_parse_custom

sample = """VALID: true
ANOMALY: Asks applicants to pay a processing fee | The posting asks for 500 peso fee before starting | high
END ANOMALIES
ATTRIBUTES:
COMPANY: Acme Corporation
LOCATION: Quezon City
END ATTRIBUTES"""

result = lm_parse_custom(sample)
print('lm_client _parse_custom result:', result)
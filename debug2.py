import sys
sys.path.insert(0, r'D:\Program Files\Downloads\Thesis\traba-hero\backend')

import app.services.scanner.verification_flow as vf

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
The posting offers a data entry role.
END POSTING ANALYSIS
JOB SUMMARY:
Daily work.
END JOB SUMMARY"""

# Monkey-patch to add debug
original = vf._parse_custom_verify

def debug_parse(text):
    import re
    result = {
        "valid": None,
        "items": [],
        "attributes": {},
        "search_queries": [],
        "employer_name": "",
        "posting_analysis": "",
        "job_summary": "",
    }

    lines = text.splitlines()
    i = 0
    in_anomalies = False
    in_attributes = False
    in_search_queries = False
    current_anomaly = None

    while i < len(lines):
        line = lines[i].strip()
        i += 1
        upper = line.upper()

        print(f'Line {i-1}: "{line}" -> upper="{upper}", in_attrs={in_attributes}, in_search={in_search_queries}')

        # VALID: true/false
        if upper.startswith("VALID:"):
            result["valid"] = upper[len("VALID:"):].strip().lower() == "true"
            print(f'  -> Handled VALID')
            continue

        # ANOMALY: label | reasoning | severity
        if upper.startswith("ANOMALY:"):
            in_anomalies = True
            current_anomaly = {"label": "", "status": "", "reasoning": ""}
            parts = line[len("ANOMALY:"):].strip().split("|")
            if len(parts) >= 1:
                current_anomaly["label"] = parts[0].strip()
            if len(parts) >= 2:
                current_anomaly["reasoning"] = parts[1].strip()
            if len(parts) >= 3:
                current_anomaly["status"] = parts[2].strip()
            print(f'  -> Handled ANOMALY: label={current_anomaly["label"]}, status={current_anomaly["status"]}')
            continue

        # END ANOMALIES
        if upper == "END ANOMALIES":
            if current_anomaly and current_anomaly.get("label") and current_anomaly.get("status"):
                result["items"].append({
                    "label": current_anomaly["label"],
                    "status": current_anomaly["status"],
                    "explanation": current_anomaly.get("reasoning", ""),
                })
            current_anomaly = None
            in_anomalies = False
            print(f'  -> Handled END ANOMALIES')
            continue

        # ATTRIBUTES: section
        if upper.startswith("ATTRIBUTES:"):
            in_attributes = True
            print(f'  -> Handled ATTRIBUTES: header, in_attributes={in_attributes}')
            continue

        # END ATTRIBUTES
        if upper == "END ATTRIBUTES":
            in_attributes = False
            result["attributes"] = {}
            print(f'  -> Handled END ATTRIBUTES, in_attributes={in_attributes}')
            continue

        # SEARCH QUERIES: section
        if upper.startswith("SEARCH QUERIES:"):
            in_search_queries = True
            print(f'  -> Handled SEARCH QUERIES: header, in_search_queries={in_search_queries}')
            continue

        # END SEARCH QUERIES
        if upper == "END SEARCH QUERIES":
            in_search_queries = False
            if len(result["search_queries"]) > 2:
                result["search_queries"] = result["search_queries"][:2]
            print(f'  -> Handled END SEARCH QUERIES, queries={result["search_queries"]}')
            continue

        # EMPLOYER NAME:
        if upper.startswith("EMPLOYER NAME:"):
            result["employer_name"] = line[len("EMPLOYER NAME:"):].strip()
            print(f'  -> Handled EMPLOYER NAME: {result["employer_name"]}')
            continue

        # POSTING ANALYSIS: section
        if upper.startswith("POSTING ANALYSIS:"):
            result["posting_analysis"] = ""
            print(f'  -> Handled POSTING ANALYSIS: header')
            continue

        # END POSTING ANALYSIS
        if upper == "END POSTING ANALYSIS":
            print(f'  -> Handled END POSTING ANALYSIS')
            continue

        # JOB SUMMARY:
        if upper.startswith("JOB SUMMARY:"):
            result["job_summary"] = ""
            print(f'  -> Handled JOB SUMMARY: header')
            continue

        # END JOB SUMMARY
        if upper == "END JOB SUMMARY":
            print(f'  -> Handled END JOB SUMMARY')
            continue

        # In anomalies
        if in_anomalies and current_anomaly is not None:
            if current_anomaly["reasoning"]:
                current_anomaly["reasoning"] += " " + line
            else:
                current_anomaly["reasoning"] = line
            print(f'  -> Anomaly detail: {line[:30]}...')
            continue

        # In attributes - THIS IS THE KEY CHECK
        if in_attributes and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().upper()
            value = value.strip()
            print(f'  -> ATTRIBUTE PARSE: KEY={key}, VALUE="{value}"')
            attr_map = {
                "COMPANY": "COMPANY",
                "LOCATION": "LOCATION",
                "CONTACT_METHOD": "CONTACT_METHOD",
                "MEETING_SPOT": "MEETING_SPOT",
                "PAY": "PAY",
                "REGISTERED_AS": "REGISTERED_AS",
            }
            if key in attr_map:
                result["attributes"][attr_map[key]] = value
                print(f'    -> Mapped to {attr_map[key]}')
            else:
                print(f'    -> Key {key} not in attr_map, skipping')
            continue

        # In search queries
        if in_search_queries and line.startswith("QUERY:"):
            result["search_queries"].append(line[len("QUERY:"):].strip())
            print(f'  -> QUERY: {line[len("QUERY:"):].strip()}')
            continue

        # Posting analysis collection
        posting_keywords = [
            "VALID:", "ANOMALY:", "END ANOMALIES", "ATTRIBUTES:", "END ATTRIBUTES",
            "SEARCH QUERIES:", "END SEARCH QUERIES", "EMPLOYER NAME:",
            "POSTING ANALYSIS:", "END POSTING ANALYSIS",
            "JOB SUMMARY:", "END JOB SUMMARY"
        ]
        if result["posting_analysis"] is not None and upper not in posting_keywords and line:
            if result["posting_analysis"]:
                result["posting_analysis"] += " " + line
            else:
                result["posting_analysis"] = line
            print(f'  -> Posting analysis: {line[:30]}...')
            continue

        # Job summary collection
        job_keywords = [
            "VALID:", "ANOMALY:", "END ANOMALIES", "ATTRIBUTES:", "END ATTRIBUTES",
            "SEARCH QUERIES:", "END SEARCH QUERIES", "EMPLOYER NAME:",
            "POSTING ANALYSIS:", "END POSTING ANALYSIS",
            "JOB SUMMARY:", "END JOB SUMMARY"
        ]
        if result["job_summary"] is not None and upper not in job_keywords and line:
            if result["job_summary"]:
                result["job_summary"] += " " + line
            else:
                result["job_summary"] = line
            print(f'  -> Job summary: {line[:30]}...')
            continue

    result["posting_analysis"] = result["posting_analysis"].strip() if result["posting_analysis"] else ""
    result["job_summary"] = result["job_summary"].strip() if result["job_summary"] else ""
    return result


result = debug_parse(sample)
print()
print('=== RESULT ===')
print('valid:', result['valid'])
print('items:', result['items'])
print('attributes:', result['attributes'])
print('search_queries:', result['search_queries'])
print('employer_name:', result['employer_name'])
print('posting_analysis:', result['posting_analysis'])
print('job_summary:', result['job_summary'])
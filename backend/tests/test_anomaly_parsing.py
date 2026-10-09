"""The parser must read the anomaly line the prompt now asks for.

`SYSTEM_PROMPT.md` and `SCAN_FORMAT_BLOCK` both emit `ANOMALY:`. The parser
recognises it as a section keyword, so a scan that produces anomalies still
scores them. These tests exist because the rename touched a parser that is
already known to be order-sensitive and to swallow sections when a marker is
misspelled — the failure is silent, showing a clean posting rather than an error.
"""

from app.services.lm_client import _parse_custom


def _score(flags):
    return None if flags == [] else flags[0]


def test_the_new_anomaly_keyword_parses():
    raw = (
        "VALID: true\n"
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high\n"
        "END ANOMALIES\n"
        "EMPLOYER NAME: Acme\n"
        "END JOB SUMMARY"
    )
    result = _parse_custom(raw)

    assert result is not None
    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["flag"] == "Asks applicants to pay a processing fee"
    assert result["anomalies"][0]["severity"] == "high"
    assert result["company_name"] == "Acme"


def test_end_anomalies_is_a_terminator_not_a_section():
    """The END marker must not reset the parser.

    It is a bare terminator for the anomaly lines. Treating it as a section end
    used to clear `matched_any`, which made a valid scan parse as nothing at
    all — the panel then showed a posting with zero findings and no error.
    """
    raw = "VALID: true\nEND ANOMALIES\nEMPLOYER NAME: Acme\n"
    result = _parse_custom(raw)

    assert result is not None
    assert result["valid"] is True


def test_the_plural_form_also_parses():
    """A model asked for one line may emit the plural.

    `ANOMALIES:` is accepted so a model that pluralises is not silently read as
    a posting with no findings.
    """
    result = _parse_custom("VALID: true\nANOMALIES: Asks for money | A fee | high\n")

    assert result is not None
    assert len(result["anomalies"]) == 1


def test_a_pre_rename_scan_still_parses():
    """Recorded output from before the rename must keep parsing.

    History holds scans captured under the old keyword, and a reader opening an
    old entry should see its findings rather than a posting that looks clean.
    """
    result = _parse_custom("VALID: true\nRED FLAG: Asks for money | A fee | high\n")

    assert result is not None
    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["severity"] == "high"


class TestPlaceholdersDoNotBecomeFindings:
    """A model told "no anomalies" often answers with a placeholder line.

    A placeholder that survives parsing becomes a finding about nothing, and it
    carries a severity, so it adds to the score. Both spellings are listed
    because a model asked for one may answer with either.
    """

    def test_a_placeholder_value_is_dropped(self):
        for value in (
            "No anomalies",
            "No anomalies detected",
            "No significant anomalies",
            "None detected",
            "N/A",
            "Legitimate",
            "No red flags detected",
        ):
            result = _parse_custom(f"VALID: true\nANOMALY: {value} | r | high\n")
            assert result["anomalies"] == [], f"{value!r} was read as a finding"

    def test_a_placeholder_prefix_is_dropped(self):
        """The check is a prefix test, because a model may add words.

        "No anomalies were found in this posting" is the same statement as "No
        anomalies", and an exact-match list would score it at high severity.
        """
        for value in (
            "No anomalies were found in this posting",
            "No significant anomalies identified",
            "No red flags present",
        ):
            result = _parse_custom(f"VALID: true\nANOMALY: {value} | r | high\n")
            assert result["anomalies"] == [], f"{value!r} was read as a finding"

    def test_a_real_anomaly_is_not_dropped(self):
        """The overcorrection: a filter loose enough to swallow real findings.

        "No visible evidence of money requests" begins with "No visible", not
        "no anomal"/"no red flag", so it must survive. If a broadening of the
        prefix list ever catches this, the filter has started discarding
        evidence.
        """
        result = _parse_custom(
            "VALID: true\nANOMALY: No visible evidence of a money request | The post describes duties only | low\n"
        )

        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["severity"] == "low"


def test_severity_is_still_inferred_when_omitted():
    """Unchanged behaviour, kept because the rename moved the branch it sits in."""
    result = _parse_custom("VALID: true\nANOMALY: Asks for an upfront fee | Pay before work | high\n")

    assert result["anomalies"][0]["severity"] == "high"

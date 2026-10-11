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


class TestPostingAttributes:
    """The scan must report what the posting claims, not only who it names.

    This is what makes dynamic retrieval possible: a query can only be built
    from a detail the posting actually states, so the detail has to be stated.
    """

    def test_attributes_parse(self):
        raw = (
            "VALID: true\n"
            "ATTRIBUTES:\n"
            "COMPANY: Tanika\n"
            "LOCATION: Maingate Terminal\n"
            "CONTACT_METHOD: personal Gmail\n"
            "MEETING_SPOT: Maingate Terminal\n"
            "PAY: 26,000 monthly\n"
            "END ATTRIBUTES\n"
            "EMPLOYER NAME: Tanika\n"
        )
        result = _parse_custom(raw)
        assert result is not None
        assert result["attributes"]["LOCATION"] == "Maingate Terminal"
        assert result["attributes"]["CONTACT_METHOD"] == "personal Gmail"

    def test_a_missing_attribute_is_not_emitted(self):
        """A missing detail must not become an empty string.

        An empty LOCATION would otherwise read as "the posting stated no
        location", which is a different claim from "the posting said nothing
        about location" — and it would generate a query that cannot succeed.
        """
        raw = "VALID: true\nATTRIBUTES:\nCOMPANY: Tanika\nEND ATTRIBUTES\n"
        result = _parse_custom(raw)
        assert "LOCATION" not in result["attributes"]
        assert "Not stated" not in result["attributes"].values()

    def test_end_attributes_does_not_reset_the_parser(self):
        raw = "VALID: true\nATTRIBUTES:\nCOMPANY: Tanika\nEND ATTRIBUTES\nEMPLOYER NAME: Tanika\n"
        result = _parse_custom(raw)
        assert result["company_name"] == "Tanika"

    def test_query_ref_attaches_to_the_preceding_anomaly(self):
        """Without this, corroboration is not computable.

        The scoring stage must know which search a finding came from, or it
        cannot tell "confirms something already counted" from "reveals
        something new" — and the double-count returns silently.
        """
        raw = (
            "VALID: true\n"
            "ANOMALY: Asks applicants to pay a fee | The post asks for a fee | high\n"
            "QUERY_REF: Acme processing fee Philippines\n"
            "ANOMALY: Generic job title | Title says 'worker' | low\n"
        )
        result = _parse_custom(raw)
        first, second = result["anomalies"]
        assert first["query_ref"] == "Acme processing fee Philippines"
        assert second["query_ref"] == ""

    def test_query_ref_after_the_last_anomaly_does_not_crash(self):
        raw = "VALID: true\nANOMALY: A fee | r | high\nQUERY_REF: orphan query\n"
        result = _parse_custom(raw)
        assert result["anomalies"][0]["query_ref"] == "orphan query"

    def test_a_query_line_is_no_longer_a_section(self):
        """The model-authored query family is gone, and this is the tombstone.

        It was parsed, capped at three, shipped on `ScanResponse.search_queries`,
        and governed by two prompt rules -- and nothing read it. `search.py`
        builds the queries instead, deterministically, from the attributes above.

        Asserted as behaviour rather than as an absent key: a `QUERY:` line is now
        ordinary prose. If it ever starts matching again, it becomes a section and
        one of the two assertions below fails.
        """
        raw = (
            "VALID: true\nSEARCH QUERIES:\n"
            "QUERY: one Philippines\nQUERY: two Philippines\n"
            "END SEARCH QUERIES\nEMPLOYER NAME: Tanika\n"
        )
        result = _parse_custom(raw)

        assert "search_queries" not in result
        # The employer path must still work beside it, or this would pass for a
        # parser that simply stopped reading everything.
        assert result["company_name"] == "Tanika"

    # ── Added beyond the brief ────────────────────────────────────────────
    # The two tests below are not in the brief. Each exists because its named
    # mutation target passed anyway: the original input never contained the
    # construct the assertion is about, so the test could not fail. See
    # task-1-report.md.

    def test_a_stated_placeholder_attribute_is_dropped(self):
        """The real gap in `test_a_missing_attribute_is_not_emitted`.

        That test's input contains no LOCATION line at all, so a parser that
        stores every attribute it sees as an empty string passes it unchanged.
        A blank value or the literal "Not stated" — the two ways the prompt tells
        the model to say nothing. Other placeholder words ("none") are NOT
        filtered here: they are passed through and dropped downstream by
        `build_scheme_queries`, so the parser's contract stays as narrow as the
        prompt's own instruction to omit the line.
        """
        for line in ("LOCATION:", "LOCATION: Not stated"):
            raw = f"VALID: true\nATTRIBUTES:\nCOMPANY: Tanika\n{line}\nEND ATTRIBUTES\n"
            result = _parse_custom(raw)
            assert "LOCATION" not in result["attributes"], f"{line!r} became an attribute"

    def test_a_second_query_ref_attaches_to_its_own_anomaly(self):
        """The real gap in `test_query_ref_attaches_to_the_preceding_anomaly`.

        That input carries one QUERY_REF, so an implementation that always
        attaches to the *first* anomaly produces identical output and passes.
        Two refs are what separate "the preceding anomaly" from "the first
        anomaly" — and that is the distinction the scoring stage depends on,
        since attaching a ref to the wrong finding credits the wrong search.
        """
        raw = (
            "VALID: true\n"
            "ANOMALY: Asks applicants to pay a fee | The post asks for a fee | high\n"
            "QUERY_REF: Acme processing fee Philippines\n"
            "ANOMALY: Meet at an unusual location | Says Maingate Terminal | mid\n"
            "QUERY_REF: Acme Maingate Terminal Philippines\n"
        )
        first, second = _parse_custom(raw)["anomalies"]
        assert first["query_ref"] == "Acme processing fee Philippines"
        assert second["query_ref"] == "Acme Maingate Terminal Philippines"

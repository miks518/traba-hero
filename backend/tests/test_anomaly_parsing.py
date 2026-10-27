"""The parser must read the anomaly line the prompt now asks for.

`SYSTEM_PROMPT.md` and `SCAN_FORMAT_BLOCK` both emit `ANOMALY:`. The parser
recognises it as a section keyword, so a scan that produces anomalies still
carries them into the verification stage. These tests exist because the parser
is already known to be order-sensitive and to swallow sections when a marker is
misspelled — the failure is silent, showing a clean posting rather than an error.
"""

from app.services.lm_client import _parse_custom


def test_the_new_anomaly_keyword_parses():
    raw = (
        "VALID: true\n"
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee\n"
        "END ANOMALIES\n"
        "EMPLOYER NAME: Acme\n"
        "END JOB SUMMARY"
    )
    result = _parse_custom(raw)

    assert result is not None
    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["flag"] == "Asks applicants to pay a processing fee"
    assert result["anomalies"][0]["reasoning"] == "The post asks for a fee"
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
    result = _parse_custom("VALID: true\nANOMALIES: Asks for money | A fee\n")

    assert result is not None
    assert len(result["anomalies"]) == 1


def test_a_pre_rename_scan_still_parses():
    """Recorded output from before the rename must keep parsing.

    History holds scans captured under the old keyword, and a reader opening an
    old entry should see its findings rather than a posting that looks clean.
    Old lines carried a trailing severity; the parser reads the reasoning and
    ignores the rest.
    """
    result = _parse_custom("VALID: true\nRED FLAG: Asks for money | A fee | high\n")

    assert result is not None
    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["reasoning"] == "A fee"


def test_a_legacy_three_part_line_parses_with_the_reasoning_intact():
    """A model that kept the old severity habit still yields a finding.

    The prompt asks for two slots, but a third one must not corrupt the
    reasoning or resurrect a field the wire no longer carries.
    """
    result = _parse_custom("VALID: true\nANOMALY: Asks for money | A fee | high\n")

    assert result["anomalies"][0]["reasoning"] == "A fee"
    assert "severity" not in result["anomalies"][0]


class TestPlaceholdersDoNotBecomeFindings:
    """A model told "no anomalies" often answers with a placeholder line.

    A placeholder that survives parsing becomes a finding about nothing. Both
    spellings are listed because a model asked for one may answer with either.
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
            result = _parse_custom(f"VALID: true\nANOMALY: {value} | r\n")
            assert result["anomalies"] == [], f"{value!r} was read as a finding"

    def test_a_placeholder_prefix_is_dropped(self):
        """The check is a prefix test, because a model may add words.

        "No anomalies were found in this posting" is the same statement as "No
        anomalies", and an exact-match list would let it through.
        """
        for value in (
            "No anomalies were found in this posting",
            "No significant anomalies identified",
            "No red flags present",
        ):
            result = _parse_custom(f"VALID: true\nANOMALY: {value} | r\n")
            assert result["anomalies"] == [], f"{value!r} was read as a finding"

    def test_a_real_anomaly_is_not_dropped(self):
        """The overcorrection: a filter loose enough to swallow real findings.

        "No visible evidence of money requests" begins with "No visible", not
        "no anomal"/"no red flag", so it must survive. If a broadening of the
        prefix list ever catches this, the filter has started discarding
        evidence.
        """
        result = _parse_custom(
            "VALID: true\nANOMALY: No visible evidence of a money request | The post describes duties only\n"
        )

        assert len(result["anomalies"]) == 1


def test_the_parsed_anomaly_carries_no_severity():
    """Tombstone for the severity field.

    The scan's high/mid/low ladder was removed because nothing downstream
    decided anything by it — see `docs/decisions/scan-severity-removal.md`.
    The parser must not quietly keep emitting a key the schema dropped, or a
    reader would reasonably conclude the number still means something.
    """
    result = _parse_custom("VALID: true\nANOMALY: Asks for an upfront fee | Pay before work\n")

    assert result["anomalies"], "the finding itself must still parse"
    assert "severity" not in result["anomalies"][0]


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

    def test_a_query_line_is_read_as_a_search(self):
        """The model-authored query family is back, and this says why.

        It was deleted in 413a2cd for the right reason - parsed, capped, shipped
        on `ScanResponse`, and read by nothing - which is not the same as it
        being a bad idea. `VerifyRequest.search_queries` now carries it to
        `/api/verify`, which issues it in place of the scheme queries this
        module used to build.

        The cap is 2 rather than the old 3, because one request is spent on the
        employer itself and the free tier is 1,000 credits a month.
        """
        raw = (
            "VALID: true\nSEARCH QUERIES:\n"
            "QUERY: Tanika branch\nQUERY: Tanika permit\nQUERY: Tanika third\n"
            "END SEARCH QUERIES\nEMPLOYER NAME: Tanika\n"
        )
        result = _parse_custom(raw)

        assert result["search_queries"] == ["Tanika branch", "Tanika permit"]
        # The employer path must still work beside it, or this would pass for a
        # parser that simply stopped reading everything.
        assert result["company_name"] == "Tanika"

    def test_the_cap_is_two(self):
        """Three would make the employer query a fourth request."""
        raw = (
            "VALID: true\nSEARCH QUERIES:\n"
            "QUERY: one\nQUERY: two\nQUERY: three\n"
            "END SEARCH QUERIES\n"
        )

        assert len(_parse_custom(raw)["search_queries"]) == 2

    def test_a_placeholder_is_not_a_query(self):
        """The model answering "none" is answering the format, not proposing a
        search. A query for "none" is a credit spent to learn nothing."""
        raw = (
            "VALID: true\nSEARCH QUERIES:\n"
            "QUERY: none\nQUERY: n/a\nQUERY: Tanika branch\n"
            "END SEARCH QUERIES\n"
        )

        assert _parse_custom(raw)["search_queries"] == ["Tanika branch"]

    def test_a_query_line_in_a_section_body_is_prose(self):
        """`QUERY` back in the alternation makes it a section keyword, and the
        branch handling it would close whatever section was open - truncating
        the summary. The guard is the same shape as the attribute gate's: a
        keyword outside its block is appended back to the buffer.
        """
        raw = (
            "VALID: true\nJOB SUMMARY:\n"
            "A crew role at a warehouse.\n"
            "QUERY: crew recruitment\n"
            "END JOB SUMMARY\n"
        )
        result = _parse_custom(raw)

        assert "crew recruitment" in result["job_summary"], (
            "a QUERY: line was treated as a section keyword and truncated the "
            "summary it appeared in"
        )
        # Prose, not a proposal: it never opened the block.
        assert result["search_queries"] == []

    def test_attributes_survive_a_missing_header(self):
        """A model that drops the `ATTRIBUTES:` header must still report.

        These attributes are what `build_scheme_queries` reads. Discarding them
        when the header is absent means zero scheme queries, and leaves
        `Location / Branch`, `Channel Match` and `Similar Offers`
        structurally unfireable — the same symptom as the extension never
        forwarding them, arriving by another route and with no error anywhere.

        Safe to read here because the two cases are distinguishable: a key
        inside a block is preceded by `ATTRIBUTES:`, and prose can only reach
        the same branch while a *section* is open. A bare attribute line at the
        top of a response has neither.
        """
        raw = (
            "VALID: true\n"
            "COMPANY: Tanika\n"
            "LOCATION: Maingate Terminal\n"
            "EMPLOYER NAME: Tanika\n"
        )
        result = _parse_custom(raw)

        assert result["attributes"]["LOCATION"] == "Maingate Terminal"
        assert result["attributes"]["COMPANY"] == "Tanika"
        assert result["company_name"] == "Tanika"

    def test_a_query_line_inside_the_attributes_block_is_not_an_attribute(self):

        """The same line inside ATTRIBUTES, where a match would have been silent.

        `in_attributes` is the gate, and this is the case where the gate is open.
        A stray `QUERY:` here used to be harvested into `attributes` under a key
        nothing queries, which is how a value reached the claims block with
        nothing in the posting behind it.
        """
        raw = "VALID: true\nATTRIBUTES:\nQUERY: Tanika scam recruitment\nEND ATTRIBUTES\n"
        result = _parse_custom(raw)

        assert "QUERY" not in result["attributes"]
        assert result["attributes"] == {}

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


class TestRepeatableAttributeKeys:
    """A repeated attribute line must add to the value, not replace it.

    `CONTACT_METHOD` is written once per channel, because a posting that gives
    two ways to apply has to be able to say so — and one of them being a free
    mail domain while the other is the employer's own is the whole observation.
    A plain `attributes[key] = value` keeps only the last line, so the first
    channel vanishes and the one check that can detect an impersonation is fed
    a third of what the posting actually said.

    Joins with `"; "` because the value is a plain string everywhere downstream:
    `VerifyRequest.attributes`, the extension's `Record<string, string>`, and the
    claims block the verify prompt quotes back. A scan recorded before this
    change has one channel and is untouched — nothing to join.
    """

    def test_a_repeated_attribute_key_accumulates(self):
        raw = (
            "VALID: true\n"
            "ATTRIBUTES:\n"
            "CONTACT_METHOD: email | hrmo6@ched.gov.ph\n"
            "CONTACT_METHOD: email | recruitment.ched@outlook.com\n"
            "CONTACT_METHOD: form | bit.ly/ChedRegionForm\n"
            "END ATTRIBUTES\n"
            "EMPLOYER NAME: Commission on Higher Education\n"
        )
        value = _parse_custom(raw)["attributes"]["CONTACT_METHOD"]
        assert "hrmo6@ched.gov.ph" in value
        assert "recruitment.ched@outlook.com" in value
        assert "bit.ly/ChedRegionForm" in value

    def test_a_single_line_is_unchanged(self):
        raw = (
            "VALID: true\nATTRIBUTES:\n"
            "CONTACT_METHOD: email | hr@harborlight.example\n"
            "END ATTRIBUTES\nEMPLOYER NAME: Harbor Light Trading\n"
        )
        assert _parse_custom(raw)["attributes"]["CONTACT_METHOD"] == (
            "email | hr@harborlight.example"
        )

    def test_other_keys_still_take_the_last_value(self):
        """Only CONTACT_METHOD is repeatable.

        Accumulating everything would silently merge two LOCATION lines into one
        unparseable value, which is a worse failure than a last-one-wins the
        prompt already discourages by saying to omit the line rather than
        repeat it.
        """
        raw = (
            "VALID: true\nATTRIBUTES:\nLOCATION: Cebu\nLOCATION: Manila\n"
            "END ATTRIBUTES\nEMPLOYER NAME: Acme\n"
        )
        assert _parse_custom(raw)["attributes"]["LOCATION"] == "Manila"

    def test_claimed_type_is_read(self):
        raw = (
            "VALID: true\nATTRIBUTES:\nCLAIMED_TYPE: government\n"
            "END ATTRIBUTES\nEMPLOYER NAME: Commission on High Learning\n"
        )
        assert _parse_custom(raw)["attributes"]["CLAIMED_TYPE"] == "government"

    def test_job_title_is_read(self):
        """The planner's row 2 is `"<role> <employer>"`, and it has no other source.

        `JOB_TITLE` is not in the ATTRIBUTES block and never appears anywhere
        else in the response, so a parser that drops the key does not fail — the
        prompt simply asks `<employer> hiring`, which is the generic lookup
        Round 1 already ran, and the row buys a credit for a question already
        answered. Asserted here because that failure is invisible everywhere
        else.
        """
        raw = (
            "VALID: true\nATTRIBUTES:\nJOB_TITLE: Project Technical Staff I\n"
            "END ATTRIBUTES\nEMPLOYER NAME: Commission on High Learning\n"
        )
        assert _parse_custom(raw)["attributes"]["JOB_TITLE"] == "Project Technical Staff I"

    def test_job_title_survives_alongside_the_claimed_type(self):
        """Two new keys in one block, since a partial edit to the keyword list
        would leave one working and one silently absent."""
        raw = (
            "VALID: true\nATTRIBUTES:\nJOB_TITLE: Barangay Health Worker\n"
            "CLAIMED_TYPE: government\n"
            "END ATTRIBUTES\nEMPLOYER NAME: Commission on High Learning\n"
        )
        parsed = _parse_custom(raw)["attributes"]
        assert parsed["JOB_TITLE"] == "Barangay Health Worker"
        assert parsed["CLAIMED_TYPE"] == "government"

    def test_the_keyword_list_and_the_regex_agree(self):
        """Two enumerations of the same keys, which is one too many.

        `_ATTRIBUTE_KEYWORDS` gates what counts as an attribute;
        `_SECTION_RE`'s alternation decides what a line even *is*. Add a key to
        the first and not the second and the line parses as prose and is
        dropped — no error, no warning, and a prompt that asks for a field the
        pipeline silently discards. `JOB_TITLE` was lost this way once, which is
        why the agreement is asserted rather than assumed.
        """
        from app.services.lm_client import _ATTRIBUTE_KEYWORDS, _SECTION_RE

        for key in _ATTRIBUTE_KEYWORDS:
            probe = _SECTION_RE.match(f"{key}: a value")
            assert probe is not None, f"{key} is a keyword the regex cannot match"
            assert probe.group("kw").upper().replace(" ", "_") == key, (
                f"{key} matches as {probe.group('kw')!r}"
            )
            assert probe.group("rest") == "a value", (
                f"{key} swallows its own value: rest={probe.group('rest')!r}"
            )


class TestProseIsNotAKeyword:
    """An attribute key only means an attribute inside the ATTRIBUTES block.

    `COMPANY`, `LOCATION` and `PAY` are words the model also uses in ordinary
    sentences. Outside the block, `Company states applicants should bring their
    own laptop.` is prose. Reading it as a key did two things at once: it stored
    the sentence in `attributes`, which `build_scheme_queries` then turned into
    a wasted credit on a query nothing can succeed at, and -- because a matched
    keyword always closes the section first -- it truncated POSTING ANALYSIS at
    that line. The assessment the reader is told to act on lost its second half
    with nothing anywhere reporting it.

    The colon is optional in `_SECTION_RE` for every key, so requiring one would
    not fix this: prose carries colons too. The block is the unit of trust.
    """

    # A POSTING ANALYSIS whose body is exactly the reported failure: three
    # sentences, the second of which begins with an attribute word.
    PROSE_ANALYSIS = (
        "POSTING ANALYSIS:\n"
        "The posting asks the applicant to pay a processing fee before work begins.\n"
        "Company states applicants should bring their own laptop.\n"
        "Location is given as Maingate Terminal.\n"
        "END POSTING ANALYSIS\n"
    )

    def test_a_sentence_beginning_with_an_attribute_word_is_not_harvested(self):
        result = _parse_custom("VALID: true\n" + self.PROSE_ANALYSIS)

        assert result["attributes"] == {}

    def test_the_assessment_is_not_truncated_at_one_of_them(self):
        """The headline symptom: "Part 2 -- the action" simply disappeared.

        Asserted on the *last* sentence, not the first. A parser that stored the
        body but stopped at the second line would keep sentence one and fail
        here, and a parser that never closed the section at all would fail the
        attribute assertion above. Both halves are needed for the pair to have
        teeth.
        """
        result = _parse_custom("VALID: true\n" + self.PROSE_ANALYSIS)

        analysis = result["posting_analysis"]
        assert analysis is not None
        assert "pay a processing fee before work begins" in analysis
        assert "bring their own laptop" in analysis
        assert "Maingate Terminal" in analysis

    def test_the_same_prose_in_a_job_summary_is_not_harvested(self):
        """Before the fix this produced an *absent* `job_summary`.

        The JOB SUMMARY section was opened, the first line matched `PAY`, the
        section closed with an empty buffer, and `close_section` skips writing a
        key at all when the buffer is empty. The summary was not truncated --
        it was gone, with no error, so the panel rendered a posting with no
        description of the role.
        """
        raw = (
            "VALID: true\n"
            "JOB SUMMARY:\n"
            "The post offers a crew role.\n"
            "Pay is 26,000 monthly for a crew role.\n"
            "END JOB SUMMARY\n"
        )
        result = _parse_custom(raw)

        assert "job_summary" in result, "the whole summary went missing, not just its tail"
        assert "26,000 monthly" in result["job_summary"]
        assert result["attributes"] == {}

    def test_an_attribute_word_after_the_block_has_ended_is_not_read(self):
        """`in_attributes` is cleared by the next keyword, not just by the marker.

        An implementation that cleared it only on `END ATTRIBUTES` would keep
        harvesting for the rest of the response, including the assessment.

        Parametrised over **both** ways the block can end. The first version of
        this test used `END ATTRIBUTES`, which is the one closing a
        terminator-only implementation also handles — so it passed under exactly
        the mutation it claimed to guard against. A model that omits the marker
        is the ordinary case worth surviving, so that is the case asserted here.
        """
        for terminator in ("END ATTRIBUTES\n", ""):
            raw = (
                "VALID: true\n"
                "ATTRIBUTES:\n"
                "COMPANY: Tanika\n"
                f"{terminator}"
                "EMPLOYER NAME: Tanika\n"
                "POSTING ANALYSIS:\n"
                "The posting states nothing alarming.\n"
                "Pay is 26,000 monthly for a crew role.\n"
                "END POSTING ANALYSIS\n"
            )
            result = _parse_custom(raw)

            assert result is not None, terminator or "no terminator"
            # The real attribute is still read: a gate that never opens would
            # satisfy this test by reporting nothing at all.
            assert result["attributes"] == {"COMPANY": "Tanika"}, terminator or "no terminator"
            assert "PAY" not in result["attributes"], terminator or "no terminator"
            assert "26,000 monthly" in result["posting_analysis"], terminator or "no terminator"

    def test_the_gate_does_not_stop_the_block_itself_from_parsing(self):
        """The overcorrection: gating the keys everywhere rather than in the block.

        A parser that dropped every `COMPANY`/`LOCATION` line would pass all four
        tests above unchanged and ship a scan that reports nothing at all -- which
        is the state Finding 1 was about, arrived at from the other direction.
        """
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

        assert result["attributes"] == {
            "COMPANY": "Tanika",
            "LOCATION": "Maingate Terminal",
            "CONTACT_METHOD": "personal Gmail",
            "MEETING_SPOT": "Maingate Terminal",
            "PAY": "26,000 monthly",
        }

    def test_the_legacy_employer_path_is_not_gated(self):
        """`COMPANY NAME` is a different alternative and still works everywhere.

        A `COMPANY NAME:` line outside ATTRIBUTES is how a scan recorded before
        the rename still resolves its employer. It is not in `_ATTRIBUTE_KEYWORDS`
        because it is not an attribute -- and if it were, the legacy path would
        silently stop parsing.
        """
        result = _parse_custom("VALID: true\nCOMPANY NAME: Acme\n")

        assert result["company_name"] == "Acme"

from datetime import timedelta
from boussla.reconciliation import compare_transaction
from boussla.checks import compare_invoice_observations
from boussla.contracts import FindingStatus
from tests.checks.test_invoice_observations import _inputs


def reconcile(inputs):
    return compare_transaction(inputs.transaction, inputs.invoice_observations, inputs.documents, inputs.as_of)


def test_five_reconciliation_states_and_no_arbitrary_candidate():
    inputs = _inputs()
    assert reconcile(inputs).reconciliation_status == "RAPPROCHE"
    empty = inputs.model_copy(update={"invoice_observations":()})
    assert reconcile(empty).reconciliation_status == "NON_RAPPROCHE"
    single = inputs.model_copy(update={"invoice_observations":inputs.invoice_observations[:1]})
    assert reconcile(single).reconciliation_status == "EN_ATTENTE_DE_CONTREPARTIE"
    assert compare_invoice_observations(single).status is FindingStatus.INSUFFICIENT
    buyer,seller = inputs.invoice_observations
    different = seller.model_copy(update={"gross_millimes":seller.gross_millimes+1})
    assert reconcile(inputs.model_copy(update={"invoice_observations":(buyer,different)})).reconciliation_status == "ECART_DETECTE"
    duplicate = seller.model_copy(update={"observation_id":"CANDIDATE-2"})
    tx = inputs.transaction.model_copy(update={"invoice_observation_ids":(*inputs.transaction.invoice_observation_ids,"CANDIDATE-2")})
    ambiguous = reconcile(inputs.model_copy(update={"transaction":tx,"invoice_observations":(buyer,seller,duplicate)}))
    assert ambiguous.reconciliation_status == "RAPPROCHEMENT_AMBIGU"
    assert ambiguous.seller_observation_id is None and len(ambiguous.candidate_observation_ids) == 3


def multiline(inputs, changed=False, reverse=False):
    buyer,seller = inputs.invoice_observations
    bline = buyer.lines[0].model_copy(update={"line_id":"B-2","normalized_item_code":"SECOND"})
    sline = seller.lines[0].model_copy(update={"line_id":"S-2","normalized_item_code":"SECOND",
        **({"quantity":"1"} if changed else {})})
    slines = (sline,seller.lines[0]) if reverse else (seller.lines[0],sline)
    return inputs.model_copy(update={"invoice_observations":(
        buyer.model_copy(update={"lines":(*buyer.lines,bline)}),seller.model_copy(update={"lines":slines}))})


def test_second_line_conflict_is_visible_and_scored_with_sources():
    inputs = multiline(_inputs(),changed=True)
    result = reconcile(inputs)
    assert result.reconciliation_status == "ECART_DETECTE"
    assert any(field.endswith(".quantity") for field in result.difference_fields)
    finding = compare_invoice_observations(inputs)
    assert finding.status is FindingStatus.UNRESOLVED
    assert finding.reason_code == "INVOICE_LINE_QUANTITY_CONFLICT"
    assert finding.calculation_version == "V4-INVOICE-2" and finding.evidence_refs


def test_line_reordering_does_not_create_conflict_and_duplicate_keys_are_ambiguous():
    inputs = multiline(_inputs(),reverse=True)
    assert reconcile(inputs).reconciliation_status == "RAPPROCHE"
    assert compare_invoice_observations(inputs).status is FindingStatus.EXPLAINED
    buyer,seller = inputs.invoice_observations
    seller = seller.model_copy(update={"lines":(seller.lines[0],seller.lines[0])})
    ambiguous = inputs.model_copy(update={"invoice_observations":(buyer,seller)})
    assert reconcile(ambiguous).reconciliation_status == "RAPPROCHEMENT_AMBIGU"
    assert compare_invoice_observations(ambiguous).status is FindingStatus.INSUFFICIENT


def test_unconfirmed_and_future_sources_cannot_claim_a_match():
    inputs = _inputs()
    buyer,seller = inputs.invoice_observations
    unconfirmed = seller.model_copy(update={"transcription_status":"PROPOSED"})
    assert reconcile(inputs.model_copy(update={"invoice_observations":(buyer,unconfirmed)})).reconciliation_status == "NON_RAPPROCHE"
    future = seller.model_copy(update={"available_at":inputs.as_of+timedelta(days=1)})
    assert reconcile(inputs.model_copy(update={"invoice_observations":(buyer,future)})).reconciliation_status == "EN_ATTENTE_DE_CONTREPARTIE"


def test_tax_identifiers_and_decimal_quantities_ignore_display_format():
    inputs = _inputs()
    buyer,seller = inputs.invoice_observations
    seller = seller.model_copy(update={"issuer_mf_raw":" ".join(seller.issuer_mf_raw),
        "lines":(seller.lines[0].model_copy(update={"quantity":buyer.lines[0].quantity+".0"}),)})
    assert reconcile(inputs.model_copy(update={"invoice_observations":(buyer,seller)})).reconciliation_status == "RAPPROCHE"

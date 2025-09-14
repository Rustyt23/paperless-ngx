from documents.utils.date_extract import extract_date


def test_invoice_date_numeric():
    assert extract_date("Invoice Date: 1/27/25") == "2025-01-27"


def test_date_of_service_textual():
    assert extract_date("Date of Service: Aug 5 2024") == "2024-08-05"


def test_issued_iso():
    assert extract_date("Issued: 2024/12/31") == "2024-12-31"


def test_statement_date_dotted():
    assert extract_date("Statement Date: 31.08.2024") == "2024-08-31"

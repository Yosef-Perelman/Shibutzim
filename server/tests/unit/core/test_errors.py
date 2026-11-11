from app.core.errors import ErrorCode, ServiceUnavailable


def test_service_unavailable_is_a_503_with_the_assistant_code_by_default():
    error = ServiceUnavailable(message="The assistant is not available.")

    assert error.status_code == 503
    assert error.to_body() == {
        "error": {"code": "assistant_unavailable", "message": "The assistant is not available."}
    }


def test_assistant_unavailable_is_in_the_error_catalogue():
    assert ErrorCode.assistant_unavailable == "assistant_unavailable"

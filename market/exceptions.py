from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class BusinessError(APIException):
    status_code = 400
    default_code = "business_rule"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {"errors": response.data}
    return response

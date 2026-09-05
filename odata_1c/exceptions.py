class ODataError(Exception):
    pass

class ODataConnectionError(ODataError):
    pass

class ODataTimeoutError(ODataConnectionError):
    pass

class ODataAuthError(ODataError):
    pass

class ODataNotFoundError(ODataError):
    pass

class ODataValidationError(ODataError):
    pass

class ArticleNotFoundError(ODataError):
    pass

class ProductExistsError(ODataError):
    pass

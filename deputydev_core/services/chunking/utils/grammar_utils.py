from enum import Enum


class LanguageIdentifiers(Enum):
    FUNCTION_DEFINITION = "function_definition"
    CLASS_DEFINITION = "class_definition"
    FUNCTION_IDENTIFIER = "function_identifier"
    CLASS_IDENTIFIER = "class_identifier"
    DECORATOR = "decorator"
    FUNCTION_CLASS_WRAPPER = "function_class_wrapper"
    NAMESPACE = "namespace"
    DECORATED_DEFINITION = "decorated_definition"
    NAMESPACE_IDENTIFIER = "namespace_identifier"

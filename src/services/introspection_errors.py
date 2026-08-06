"""Safe errors exposed by the raw-schema extraction interface."""


class IntrospectionError(Exception):
    """Base error for schema extraction failures."""


class InvalidCredentialError(IntrospectionError):
    """Raised when encrypted credentials cannot be decrypted."""


class UnsupportedDatabaseTypeError(IntrospectionError):
    """Raised when an extraction dialect is not supported."""


class ConnectionIntrospectionError(IntrospectionError):
    """Raised when a live target database cannot be inspected."""


class SchemaIntrospectionError(IntrospectionError):
    """Raised when no requested live table can be inspected."""


class InvalidSchemaDumpError(IntrospectionError):
    """Raised when a dump is invalid or contains no table DDL."""

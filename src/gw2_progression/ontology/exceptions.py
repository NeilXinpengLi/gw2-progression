"""Ontology-specific exceptions for typed error handling."""


class OntologyError(Exception):
    """Base ontology exception."""


class ObjectNotFoundError(OntologyError):
    """Requested object does not exist in the store."""


class RelationNotFoundError(OntologyError):
    """Requested relation does not exist."""


class ValidationError(OntologyError):
    """Object or relation failed validation."""


class PreconditionFailedError(OntologyError):
    """Action preconditions were not met."""


class PersistenceError(OntologyError):
    """DB persistence failed after retries."""

"""Typed repository errors mapped to API problem responses later."""


class RepositoryError(Exception):
    """Base class for governed repository failures."""


class DecisionNotFoundError(RepositoryError):
    pass


class RevisionNotFoundError(RepositoryError):
    pass


class ApprovedRevisionNotFoundError(RepositoryError):
    pass


class AmbiguousEffectiveRevisionError(RepositoryError):
    pass


class InvalidEffectiveIntervalError(RepositoryError):
    pass


class IllegalLifecycleTransitionError(RepositoryError):
    pass


class SelfApprovalError(RepositoryError):
    pass


class SubmissionActorError(RepositoryError):
    pass


class ApprovalEvidenceError(RepositoryError):
    pass


class EffectiveIntervalOverlapError(RepositoryError):
    pass

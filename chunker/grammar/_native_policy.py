"""Identify explicit OS application-control denials without guessing from text."""

from typing import Any


APPLICATION_CONTROL_MESSAGE = (
    "Blocked by OS application-control policy: Windows rejected this native library. "
    "Unsigned or newly created files may not yet be trusted. Use a signed, "
    "organization-approved grammar build or ask your administrator to approve it "
    "under the existing application-control policy. Check the Code Integrity "
    "Operational log for event 3077. The library was not admitted."
)


def is_application_control_error(error: BaseException) -> bool:
    """Recognize explicit Windows policy errors, never generic access denials."""
    return isinstance(error, OSError) and getattr(error, "winerror", None) in {
        1260,  # ERROR_ACCESS_DISABLED_BY_POLICY
        4551,  # ERROR_SYSTEM_INTEGRITY_POLICY_VIOLATION
    }


class NativePolicyBlockedError(OSError):
    """A native load rejected by the OS application-control policy."""

    winerror: int

    def __reduce__(self) -> tuple[Any, ...]:
        # OSError's default Windows reduction can lose winerror without a filename.
        return type(self), self.args, {"winerror": self.winerror}

    def __setstate__(self, state: dict[str, Any] | None) -> None:
        if state is not None:
            self.winerror = state["winerror"]

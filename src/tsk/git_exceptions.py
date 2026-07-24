class GitError(Exception):
    """Base for all git-layer failures."""


class PushRejectedError(GitError):
    """Push rejected non-fast-forward — remote moved; fetch and retry."""

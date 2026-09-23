class GraphicsError(ValueError):
    """A graphics request is invalid or cannot be safely processed."""


class ArtifactIntegrityError(GraphicsError):
    """An existing artifact set no longer matches its recorded hashes."""

"""
Registry of ingestion sources. Both ingestion-service's CLI and
gateway-service's /matches/refresh endpoint look sources up here, so
adding a new source (another platform) means: write app/sources/<name>.py
with a fetch_all(...) function matching the existing sources' signature,
then add one line here — nothing else needs to change.
"""
SOURCE_NAMES = ["internshala", "unstop", "linkedin"]


def get_source(name: str):
    """Lazily imports and returns the source module for `name`, so callers
    that only need one source don't pay the import cost (or need the env
    vars) for the others."""
    if name == "internshala":
        from shared.ingestion.sources import internshala

        return internshala
    if name == "unstop":
        from shared.ingestion.sources import unstop

        return unstop
    if name == "linkedin":
        from shared.ingestion.sources import linkedin

        return linkedin
    raise ValueError(f"Unknown source '{name}' — expected one of {SOURCE_NAMES}")
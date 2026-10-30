"""What a provider check returns."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

OPEN = "open"            # bookable slot seen
CLOSED = "closed"        # checked fine, no slot
ERROR = "error"          # the check itself failed (network, layout change, block)
MANUAL = "manual"        # no automatic check possible; page links to the booking site


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Result:
    key: str                 # stable id, e.g. "fra/IST-ALT/tourism"
    country: str             # ISO-2 code, e.g. "FR"
    provider: str            # "vfs", "bls", ...
    status: str
    center: str = ""
    category: str = ""
    earliest: str = ""       # YYYY-MM-DD when the provider tells us
    detail: str = ""
    booking_url: str = ""
    checked_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

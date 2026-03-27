import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Config:
    PROJECT_ROOT: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    SCRIPTS_DIR: Path = field(init=False)
    DATA_DIR: Path = field(init=False)
    OUTPUT_DIR: Path = field(init=False)
    HISTORY_DIR: Path = field(init=False)
    REVIEW_PT_DIR: Path = field(init=False)
    DATE_STR: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    TODAY: object = field(default_factory=lambda: datetime.now().date())
    iteration_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self):
        self.SCRIPTS_DIR   = self.PROJECT_ROOT / "scripts"
        self.DATA_DIR      = self.PROJECT_ROOT / "data"
        self.OUTPUT_DIR    = self.DATA_DIR / "output"
        self.HISTORY_DIR   = self.OUTPUT_DIR / "history"
        self.REVIEW_PT_DIR = self.OUTPUT_DIR / "review" / "pt"

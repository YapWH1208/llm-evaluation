from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TextSample:
    sample_id: str
    prompt: str
    reference_answer: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TextQuickCheck:
    identifier: str
    version: str
    display_name: str
    samples: tuple[TextSample, ...]


TEXT_QUICK_CHECK = TextQuickCheck(
    identifier="text-quick-check",
    version="1.0.0",
    display_name="Text Quick Check",
    samples=(
        TextSample(
            sample_id="arithmetic-001",
            prompt="Reply with only the number: what is 2 + 2?",
            reference_answer="4",
            metadata={"capability": "reasoning", "language": "en", "difficulty": "basic"},
        ),
        TextSample(
            sample_id="instruction-001",
            prompt="Reply with only the word BLUE in uppercase.",
            reference_answer="BLUE",
            metadata={"capability": "instruction_following", "language": "en", "difficulty": "basic"},
        ),
        TextSample(
            sample_id="reasoning-001",
            prompt="Reply with only the number: if three birds are on a branch and one leaves, how many remain?",
            reference_answer="2",
            metadata={"capability": "reasoning", "language": "en", "difficulty": "basic"},
        ),
    ),
)

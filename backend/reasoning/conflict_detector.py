from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.schemas import Decision, DecisionStatus


@dataclass
class Conflict:
    """
    Represents a potentially conflicting pair of decisions.

    The detector identifies a conflict but does not resolve it.
    """

    conflict_id: str

    conflict_type: str

    description: str

    decision_ids: list[str] = field(
        default_factory=list
    )

    evidence_ids: list[str] = field(
        default_factory=list
    )

    confidence: float = 0.0

    status: str = "unresolved"

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type,
            "description": self.description,
            "decision_ids": self.decision_ids,
            "evidence_ids": self.evidence_ids,
            "confidence": self.confidence,
            "status": self.status,
        }


class ConflictDetector:
    """
    Detects potentially conflicting project decisions.

    Important design rule:

        The detector only identifies a potential conflict.

        It NEVER decides which decision is correct.

    Example:

        PostgreSQL vs MongoDB
            -> database conflict

        FastAPI vs Django
            -> backend framework conflict

        React vs Vue
            -> frontend framework conflict

        PostgreSQL vs Redis
            -> NOT automatically a conflict

    The detector is intentionally conservative.
    """

    # ---------------------------------------------------------
    # Decision target patterns
    # ---------------------------------------------------------

    TARGET_PATTERNS = [
        r"\buse\s+([A-Za-z0-9_.-]+)",
        r"\bchoose\s+([A-Za-z0-9_.-]+)",
        r"\bchosen\s+([A-Za-z0-9_.-]+)",
        r"\bselected\s+([A-Za-z0-9_.-]+)",
        r"\bswitch\s+to\s+([A-Za-z0-9_.-]+)",
        r"\bchange\s+to\s+([A-Za-z0-9_.-]+)",
        r"\breplace\s+.+?\s+with\s+([A-Za-z0-9_.-]+)",
    ]

    # ---------------------------------------------------------
    # Technology domains
    #
    # Technologies inside the same domain can potentially
    # conflict with each other.
    #
    # Technologies from different domains are NOT treated as
    # conflicting automatically.
    # ---------------------------------------------------------

    TECHNOLOGY_DOMAINS = {

        "database": {
            "postgresql",
            "postgres",
            "mysql",
            "mariadb",
            "mongodb",
            "mongo",
            "sqlite",
            "oracle",
            "sqlserver",
            "mssql",
            "dynamodb",
            "cassandra",
            "cockroachdb",
        },

        "cache": {
            "redis",
            "memcached",
            "hazelcast",
            "dragonfly",
        },

        "backend": {
            "django",
            "flask",
            "fastapi",
            "express",
            "nestjs",
            "spring",
            "springboot",
        },

        "frontend": {
            "react",
            "angular",
            "vue",
            "svelte",
            "nextjs",
            "next",
        },

        "language": {
            "python",
            "javascript",
            "typescript",
            "java",
            "cpp",
            "c",
            "rust",
            "go",
        },

        "framework": {
            "pytorch",
            "tensorflow",
            "keras",
            "jax",
            "scikit-learn",
        },

        "container": {
            "docker",
            "podman",
            "containerd",
        },

        "orchestration": {
            "kubernetes",
            "k8s",
            "docker-compose",
            "nomad",
        },
    }

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def detect(
        self,
        decisions: list[Decision],
    ) -> list[Conflict]:

        conflicts: list[Conflict] = []

        for index, first in enumerate(decisions):

            for second in decisions[index + 1:]:

                # Same decision object should never conflict
                if first.id == second.id:
                    continue

                conflict = self._compare_decisions(
                    first,
                    second,
                )

                if conflict is not None:
                    conflicts.append(conflict)

        return self._deduplicate(
            conflicts
        )

    # ---------------------------------------------------------
    # Compare two decisions
    # ---------------------------------------------------------

    def _compare_decisions(
        self,
        first: Decision,
        second: Decision,
    ) -> Conflict | None:

        # -----------------------------------------------------
        # Different projects cannot conflict with each other
        # -----------------------------------------------------

        if first.project != second.project:
            return None

        # -----------------------------------------------------
        # A superseded decision is historical information.
        #
        # Do not report it as an active conflict.
        # -----------------------------------------------------

        if (
            first.status
            == DecisionStatus.SUPERSEDED
        ):
            return None

        if (
            second.status
            == DecisionStatus.SUPERSEDED
        ):
            return None

        # -----------------------------------------------------
        # Extract technology targets
        # -----------------------------------------------------

        first_target = self._extract_target(
            first.decision
        )

        second_target = self._extract_target(
            second.decision
        )

        # If we cannot confidently identify the target,
        # do not guess.
        if first_target is None:
            return None

        if second_target is None:
            return None

        # -----------------------------------------------------
        # Same target is obviously not a conflict
        # -----------------------------------------------------

        if first_target == second_target:
            return None

        # -----------------------------------------------------
        # Determine domains
        # -----------------------------------------------------

        first_domain = self._get_domain(
            first_target
        )

        second_domain = self._get_domain(
            second_target
        )

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # Unknown technologies must NOT be guessed.
        #
        # This prevents false positives.
        # -----------------------------------------------------

        if first_domain is None:
            return None

        if second_domain is None:
            return None

        # -----------------------------------------------------
        # Different domains are not contradictory decisions.
        #
        # Example:
        #
        # PostgreSQL = database
        # Redis      = cache
        #
        # These can coexist in the same architecture.
        # -----------------------------------------------------

        if first_domain != second_domain:
            return None

        # -----------------------------------------------------
        # Same domain + different target
        # = potential contradiction
        # -----------------------------------------------------

        evidence_ids = list(
            dict.fromkeys(
                first.evidence_ids
                + second.evidence_ids
            )
        )

        return Conflict(
            conflict_id=(
                f"conflict_"
                f"{first.id}_"
                f"{second.id}"
            ),

            conflict_type=(
                "contradictory_decisions"
            ),

            description=(
                f"Potentially conflicting "
                f"{first_domain} decisions: "
                f"'{first.decision}' versus "
                f"'{second.decision}'."
            ),

            decision_ids=[
                first.id,
                second.id,
            ],

            evidence_ids=evidence_ids,

            confidence=0.85,

            status="unresolved",
        )

    # ---------------------------------------------------------
    # Extract selected technology
    # ---------------------------------------------------------

    @classmethod
    def _extract_target(
        cls,
        decision_text: str,
    ) -> str | None:

        if not decision_text:
            return None

        text = decision_text.strip()

        for pattern in cls.TARGET_PATTERNS:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match is None:
                continue

            target = match.group(1)

            if not target:
                continue

            target = (
                target
                .lower()
                .strip()
                .rstrip(
                    ".,;:!?)]}"
                )
            )

            return target

        return None

    # ---------------------------------------------------------
    # Find technology domain
    # ---------------------------------------------------------

    @classmethod
    def _get_domain(
        cls,
        target: str,
    ) -> str | None:

        if not target:
            return None

        normalized = (
            target
            .lower()
            .strip()
        )

        # Direct exact lookup
        for (
            domain,
            technologies,
        ) in cls.TECHNOLOGY_DOMAINS.items():

            if normalized in technologies:
                return domain

        return None

    # ---------------------------------------------------------
    # Remove duplicate conflicts
    # ---------------------------------------------------------

    @staticmethod
    def _deduplicate(
        conflicts: list[Conflict],
    ) -> list[Conflict]:

        unique: list[Conflict] = []

        seen: set[
            frozenset[str]
        ] = set()

        for conflict in conflicts:

            key = frozenset(
                conflict.decision_ids
            )

            if key in seen:
                continue

            seen.add(key)

            unique.append(
                conflict
            )

        return unique
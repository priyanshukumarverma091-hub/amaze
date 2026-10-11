from backend.reasoning import ConflictDetector
from backend.schemas import Decision, DecisionStatus


def make_decision(
    decision_id: str,
    text: str,
    evidence_id: str,
    project: str = "test/project",
    status: DecisionStatus = DecisionStatus.ACCEPTED,
):
    return Decision(
        id=decision_id,
        title="Architecture Decision",
        decision=text,
        evidence_ids=[evidence_id],
        decided_by=["developer"],
        project=project,
        status=status,
    )


# ============================================================
# TEST 1
# PostgreSQL vs MongoDB should be detected as a conflict.
# ============================================================

def test_detects_conflicting_decisions():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert len(conflicts) == 1

    conflict = conflicts[0]

    assert (
        conflict.conflict_type
        == "contradictory_decisions"
    )

    assert set(
        conflict.decision_ids
    ) == {
        "decision_1",
        "decision_2",
    }

    assert set(
        conflict.evidence_ids
    ) == {
        "evidence_1",
        "evidence_2",
    }

    assert (
        conflict.status
        == "unresolved"
    )

    assert (
        conflict.confidence
        > 0
    )


# ============================================================
# TEST 2
# Same technology should NOT be considered a conflict.
# ============================================================

def test_same_decision_is_not_conflict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert conflicts == []


# ============================================================
# TEST 3
# Decisions from different projects should NOT conflict.
# ============================================================

def test_different_projects_are_not_conflict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
        project="project/a",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
        project="project/b",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert conflicts == []


# ============================================================
# TEST 4
# Superseded decisions should be ignored.
# ============================================================

def test_superseded_decision_is_ignored():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
        status=DecisionStatus.SUPERSEDED,
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert conflicts == []


# ============================================================
# TEST 5
# PostgreSQL vs Redis should NOT conflict because they are
# different technology domains.
# ============================================================

def test_unrelated_decisions_are_not_conflict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use Redis.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert conflicts == []


# ============================================================
# TEST 6
# Empty input should return an empty list.
# ============================================================

def test_empty_decisions():

    detector = ConflictDetector()

    conflicts = detector.detect([])

    assert conflicts == []


# ============================================================
# TEST 7
# Conflict object should serialize correctly.
# ============================================================

def test_conflict_to_dict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert len(conflicts) == 1

    conflict = conflicts[0]

    result = conflict.to_dict()

    assert isinstance(
        result,
        dict,
    )

    assert (
        result["conflict_id"]
    )

    assert (
        result["conflict_type"]
        == "contradictory_decisions"
    )

    assert (
        result["description"]
    )

    assert (
        result["decision_ids"]
    )

    assert (
        result["evidence_ids"]
    )

    assert (
        result["confidence"]
        > 0
    )

    assert (
        result["status"]
        == "unresolved"
    )


# ============================================================
# TEST 8
# Duplicate decisions should not create duplicate conflicts.
# ============================================================

def test_duplicate_conflicts_are_removed():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [
            first,
            second,
            second,
        ]
    )

    assert len(conflicts) == 1


# ============================================================
# TEST 9
# Backend technologies should be compared within the same
# technology domain.
# ============================================================

def test_backend_framework_conflict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use FastAPI.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use Django.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert len(conflicts) == 1

    assert (
        conflicts[0].conflict_type
        == "contradictory_decisions"
    )


# ============================================================
# TEST 10
# Frontend technologies should be compared within the same
# technology domain.
# ============================================================

def test_frontend_framework_conflict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use React.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use Vue.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert len(conflicts) == 1


# ============================================================
# TEST 11
# Same backend technology should not conflict.
# ============================================================

def test_same_backend_framework_is_not_conflict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use FastAPI.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use FastAPI.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert conflicts == []


# ============================================================
# TEST 12
# Database decision and cache decision should not conflict.
# ============================================================

def test_database_and_cache_are_not_conflict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use Redis.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert conflicts == []


# ============================================================
# TEST 13
# Different projects with same technologies should not conflict.
# ============================================================

def test_same_technology_different_projects():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
        project="project/a",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
        project="project/b",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert conflicts == []


# ============================================================
# TEST 14
# Multiple conflicting decisions should produce multiple
# pairwise conflicts.
# ============================================================

def test_multiple_database_conflicts():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
    )

    third = make_decision(
        decision_id="decision_3",
        text="We decided to use MySQL.",
        evidence_id="evidence_3",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [
            first,
            second,
            third,
        ]
    )

    assert len(conflicts) == 3


# ============================================================
# TEST 15
# Conflict IDs should be generated.
# ============================================================

def test_conflict_id_is_generated():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert len(conflicts) == 1

    assert (
        conflicts[0].conflict_id
        == "conflict_decision_1_decision_2"
    )


# ============================================================
# TEST 16
# Detector should handle a single decision.
# ============================================================

def test_single_decision():

    decision = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [decision]
    )

    assert conflicts == []


# ============================================================
# TEST 17
# Rejected decision should still be detectable if it conflicts
# with another active decision.
# ============================================================

def test_rejected_decision_conflict():

    first = make_decision(
        decision_id="decision_1",
        text="We decided to use PostgreSQL.",
        evidence_id="evidence_1",
        status=DecisionStatus.REJECTED,
    )

    second = make_decision(
        decision_id="decision_2",
        text="We decided to use MongoDB.",
        evidence_id="evidence_2",
    )

    detector = ConflictDetector()

    conflicts = detector.detect(
        [first, second]
    )

    assert len(conflicts) == 1
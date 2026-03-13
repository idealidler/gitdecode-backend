from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


def _score_from_thresholds(value: float, thresholds: List[Tuple[float, int]]) -> int:
    for threshold, score in thresholds:
        if value >= threshold:
            return score
    return 0


@dataclass(frozen=True)
class ScoreTrace:
    category: str
    signal: str
    value: Any
    impact: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "signal": self.signal,
            "value": self.value,
            "impact": self.impact,
            "reason": self.reason,
        }


class ProfileScoringEngine:
    SENIORITY_THRESHOLDS = {
        "review_to_pr_ratio": [(0.8, 4), (0.5, 3), (0.25, 2), (0.1, 1)],
        "code_reviews_conducted": [(40, 4), (15, 3), (5, 2), (1, 1)],
        "pr_merge_ratio_pct": [(90, 3), (75, 2), (60, 1)],
        "avg_active_repo_longevity_months": [(24, 3), (12, 2), (3, 1)],
        "active_repositories_last_6_months": [(8, 2), (4, 1)],
        "commit_velocity_last_90_days": [(220, 3), (90, 2), (25, 1)],
    }

    def __init__(self, metrics_payload: Dict[str, Any]):
        self.metrics = metrics_payload
        self.traces: List[ScoreTrace] = []

    def _trace(self, category: str, signal: str, value: Any, impact: str, reason: str) -> None:
        self.traces.append(ScoreTrace(category, signal, value, impact, reason))

    def _score_seniority(self) -> Tuple[str, str, int]:
        score = 0
        m = self.metrics

        review_ratio = m.get("review_to_pr_ratio", 0.0)
        review_score = _score_from_thresholds(review_ratio, self.SENIORITY_THRESHOLDS["review_to_pr_ratio"])
        score += review_score
        if review_score >= 3:
            self._trace("seniority", "review_to_pr_ratio", review_ratio, "positive", "High review participation points toward senior/staff behavior.")
        elif review_score == 0:
            self._trace("seniority", "review_to_pr_ratio", review_ratio, "negative", "Very limited review participation weakens seniority confidence.")

        reviews = m.get("code_reviews_conducted", 0)
        reviews_score = _score_from_thresholds(reviews, self.SENIORITY_THRESHOLDS["code_reviews_conducted"])
        score += reviews_score
        if reviews_score >= 3:
            self._trace("seniority", "code_reviews_conducted", reviews, "positive", "High review volume suggests mentorship and team influence.")

        merge_ratio = m.get("pr_merge_ratio_pct", 0.0)
        merge_score = _score_from_thresholds(merge_ratio, self.SENIORITY_THRESHOLDS["pr_merge_ratio_pct"])
        score += merge_score
        if merge_score >= 2:
            self._trace("seniority", "pr_merge_ratio_pct", merge_ratio, "positive", "Strong PR merge quality indicates production alignment.")
        elif merge_score == 0 and m.get("total_recent_prs", 0) >= 5:
            self._trace("seniority", "pr_merge_ratio_pct", merge_ratio, "negative", "Low merge ratio weakens production-readiness signals.")

        longevity = m.get("avg_active_repo_longevity_months", 0.0)
        longevity_score = _score_from_thresholds(longevity, self.SENIORITY_THRESHOLDS["avg_active_repo_longevity_months"])
        score += longevity_score
        if longevity_score >= 2:
            self._trace("seniority", "avg_active_repo_longevity_months", longevity, "positive", "Longer-lived active repositories indicate system stewardship.")

        active_repos = m.get("active_repositories_last_6_months", 0)
        active_score = _score_from_thresholds(active_repos, self.SENIORITY_THRESHOLDS["active_repositories_last_6_months"])
        score += active_score
        if active_score >= 1:
            self._trace("seniority", "active_repositories_last_6_months", active_repos, "positive", "Recent activity across repositories strengthens consistency.")

        commits = m.get("commit_velocity_last_90_days", 0)
        commit_score = _score_from_thresholds(commits, self.SENIORITY_THRESHOLDS["commit_velocity_last_90_days"])
        score += commit_score
        if commit_score >= 2:
            self._trace("seniority", "commit_velocity_last_90_days", commits, "positive", "Strong recent activity supports sustained execution.")

        if score >= 15:
            label = "Staff"
        elif score >= 10:
            label = "Senior"
        elif score >= 5:
            label = "Mid-Level"
        else:
            label = "Junior"

        confidence = self._confidence_for_score(
            score=score,
            max_score=19,
            sparse_data=self._is_sparse_profile(),
            contradictory=self._has_conflicting_signals(),
        )

        self._trace("seniority", "final_score", score, "neutral", f"Deterministic seniority assigned as {label}.")
        return label, confidence, score

    def _score_execution_velocity(self) -> str:
        commits = self.metrics.get("commit_velocity_last_90_days", 0)
        active_repos = self.metrics.get("active_repositories_last_6_months", 0)
        repos_contributed = self.metrics.get("repositories_contributed_to", 0)

        if commits >= 180 or (commits >= 120 and active_repos >= 4):
            label = "Top 10% Contributor"
        elif commits >= 35 or active_repos >= 2 or repos_contributed >= 2:
            label = "Consistent Output"
        else:
            label = "Sporadic / Bursty"

        self._trace("velocity", "execution_velocity", {"commits": commits, "active_repos": active_repos}, "neutral", f"Deterministic execution velocity assigned as {label}.")
        return label

    def _score_lifecycle_fit(self) -> str:
        longevity = self.metrics.get("avg_active_repo_longevity_months", 0.0)
        if longevity < 3:
            label = "Zero-to-One / Greenfield"
        elif longevity <= 18:
            label = "Core Contributor"
        else:
            label = "Scale & Optimize"
        self._trace("lifecycle", "avg_active_repo_longevity_months", longevity, "neutral", f"Deterministic lifecycle fit assigned as {label}.")
        return label

    def _score_collaboration_profile(self) -> str:
        review_ratio = self.metrics.get("review_to_pr_ratio", 0.0)
        external_ratio = self.metrics.get("external_pr_ratio", 0.0)
        reviews = self.metrics.get("code_reviews_conducted", 0)

        if review_ratio >= 0.6 or reviews >= 25:
            return "Mentor / Reviewer"
        if external_ratio >= 0.35:
            return "Cross-team Collaborator"
        if review_ratio >= 0.2:
            return "Balanced Collaborator"
        return "Primarily Individual Contributor"

    def _score_archetype(self) -> Tuple[str, str]:
        m = self.metrics
        commits = m.get("commit_velocity_last_90_days", 0)
        active_repos = m.get("active_repositories_last_6_months", 0)
        longevity = m.get("avg_active_repo_longevity_months", 0.0)
        review_ratio = m.get("review_to_pr_ratio", 0.0)
        reviews = m.get("code_reviews_conducted", 0)
        merge_ratio = m.get("pr_merge_ratio_pct", 0.0)
        external_ratio = m.get("external_pr_ratio", 0.0)
        repos_contributed = m.get("repositories_contributed_to", 0)
        language_breadth = len(m.get("top_languages", []))
        framework_breadth = len(m.get("dominant_frameworks", []))
        breadth = language_breadth + framework_breadth

        scores = {
            "OSS Titan": 0,
            "Enterprise Architect": 0,
            "Product Builder": 0,
            "Consistent Craftsman": 0,
            "Startup Generalist": 0,
            "Deep Specialist": 0,
            "Rapid Experimenter": 0,
            "Portfolio Builder": 0,
            "Early Career Developer": 0,
        }

        scores["OSS Titan"] += 4 if external_ratio >= 0.45 else 0
        scores["OSS Titan"] += 3 if repos_contributed >= 4 else 0
        scores["OSS Titan"] += 2 if reviews >= 15 else 0

        scores["Enterprise Architect"] += 4 if longevity >= 18 else 0
        scores["Enterprise Architect"] += 3 if review_ratio >= 0.5 else 0
        scores["Enterprise Architect"] += 2 if merge_ratio >= 80 else 0

        scores["Product Builder"] += 4 if commits >= 120 else 0
        scores["Product Builder"] += 3 if active_repos >= 4 else 0
        scores["Product Builder"] += 2 if 3 <= longevity <= 18 else 0

        scores["Consistent Craftsman"] += 4 if 35 <= commits < 180 else 0
        scores["Consistent Craftsman"] += 3 if merge_ratio >= 80 else 0
        scores["Consistent Craftsman"] += 2 if review_ratio >= 0.2 else 0

        scores["Startup Generalist"] += 3 if commits >= 100 else 0
        scores["Startup Generalist"] += 3 if active_repos >= 4 else 0
        scores["Startup Generalist"] += 2 if breadth >= 5 else 0
        scores["Startup Generalist"] += 1 if longevity < 12 else 0

        scores["Deep Specialist"] += 3 if breadth <= 3 else 0
        scores["Deep Specialist"] += 3 if longevity >= 12 else 0
        scores["Deep Specialist"] += 2 if review_ratio >= 0.3 else 0

        scores["Rapid Experimenter"] += 4 if longevity < 3 else 0
        scores["Rapid Experimenter"] += 3 if active_repos >= 3 else 0
        scores["Rapid Experimenter"] += 2 if commits >= 80 else 0

        scores["Portfolio Builder"] += 4 if active_repos >= 5 else 0
        scores["Portfolio Builder"] += 3 if breadth >= 5 else 0
        scores["Portfolio Builder"] += 2 if longevity < 6 else 0
        scores["Portfolio Builder"] += 1 if review_ratio < 0.2 else 0

        scores["Early Career Developer"] += 4 if commits < 25 else 0
        scores["Early Career Developer"] += 3 if reviews < 3 else 0
        scores["Early Career Developer"] += 2 if longevity < 6 else 0
        scores["Early Career Developer"] += 2 if merge_ratio < 70 else 0

        top_archetype = max(scores, key=scores.get)
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_score = ordered[0][1]
        second_score = ordered[1][1]

        confidence = "High" if top_score - second_score >= 3 and top_score >= 7 else "Medium"
        if self._is_sparse_profile():
            confidence = "Low"

        self._trace("archetype", "archetype_scorecard", ordered[:3], "neutral", f"Deterministic archetype assigned as {top_archetype}.")
        return top_archetype, confidence

    def _derive_risk_flags(self) -> Tuple[List[str], str]:
        flags: List[str] = []
        m = self.metrics

        if m.get("review_to_pr_ratio", 0.0) < 0.15 and m.get("code_reviews_conducted", 0) < 5:
            flags.append("low review participation")
        if m.get("external_pr_ratio", 0.0) < 0.1 and m.get("repositories_contributed_to", 0) < 2:
            flags.append("low external collaboration")
        if m.get("pr_merge_ratio_pct", 0.0) < 60 and m.get("total_recent_prs", 0) >= 5:
            flags.append("low merge success")
        if m.get("avg_active_repo_longevity_months", 0.0) < 3 and m.get("active_repositories_last_6_months", 0) >= 2:
            flags.append("shallow maintenance history")
        if m.get("commit_velocity_last_90_days", 0) < 20 and m.get("active_repositories_last_6_months", 0) < 2:
            flags.append("low recent activity")

        if not flags:
            flags.append("no major deterministic risks")

        for flag in flags:
            self._trace("risk", "risk_flag", flag, "neutral", f"Deterministic risk flag added: {flag}.")

        confidence = "Low" if self._is_sparse_profile() else "High" if len(flags) <= 2 else "Medium"
        return flags, confidence

    def _is_sparse_profile(self) -> bool:
        commits = self.metrics.get("commit_velocity_last_90_days", 0)
        reviews = self.metrics.get("code_reviews_conducted", 0)
        active_repos = self.metrics.get("active_repositories_last_6_months", 0)
        recent_prs = self.metrics.get("total_recent_prs", 0)
        strong_signal_count = sum(1 for value in [commits >= 20, reviews >= 3, active_repos >= 2, recent_prs >= 3] if value)
        return strong_signal_count <= 1

    def _has_conflicting_signals(self) -> bool:
        commits = self.metrics.get("commit_velocity_last_90_days", 0)
        merge_ratio = self.metrics.get("pr_merge_ratio_pct", 0.0)
        review_ratio = self.metrics.get("review_to_pr_ratio", 0.0)
        longevity = self.metrics.get("avg_active_repo_longevity_months", 0.0)
        return (
            (commits >= 120 and merge_ratio < 55)
            or (review_ratio >= 0.5 and longevity < 3)
            or (commits < 20 and longevity >= 18)
        )

    def _confidence_for_score(self, score: int, max_score: int, sparse_data: bool, contradictory: bool) -> str:
        if sparse_data:
            return "Low"
        if contradictory:
            return "Medium"
        normalized = score / max_score if max_score else 0
        if normalized >= 0.7:
            return "High"
        if normalized >= 0.35:
            return "Medium"
        return "Low"

    def _low_signal_reason(self) -> str | None:
        if not self._is_sparse_profile():
            return None
        return "GitHub activity is sparse, so labels are deterministic but low-confidence."

    def _core_stack(self) -> List[str]:
        stack: List[str] = []
        seen: set[str] = set()
        for item in self.metrics.get("top_languages", []):
            normalized = str(item).strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                stack.append(item)
        for item in self.metrics.get("dominant_frameworks", []):
            normalized = str(item).strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                stack.append(item)
            if len(stack) >= 5:
                break
        return stack[:5]

    def generate_payload(self) -> Dict[str, Any]:
        seniority_estimate, seniority_confidence, _ = self._score_seniority()
        execution_velocity = self._score_execution_velocity()
        lifecycle_fit = self._score_lifecycle_fit()
        collaboration_profile = self._score_collaboration_profile()
        archetype, archetype_confidence = self._score_archetype()
        risk_flags, risk_confidence = self._derive_risk_flags()

        return {
            "seniority_estimate": seniority_estimate,
            "seniority_confidence": seniority_confidence,
            "archetype": archetype,
            "archetype_confidence": archetype_confidence,
            "execution_velocity": execution_velocity,
            "lifecycle_fit": lifecycle_fit,
            "collaboration_profile": collaboration_profile,
            "risk_flags": risk_flags,
            "risk_confidence": risk_confidence,
            "low_signal_reason": self._low_signal_reason(),
            "core_stack": self._core_stack(),
            "rule_trace": [trace.to_dict() for trace in self.traces],
            "raw_evidence": self.metrics,
        }

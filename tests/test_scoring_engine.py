import unittest
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from scoring_engine import ProfileScoringEngine


def payload(**overrides):
    base = {
        "name": "Test User",
        "commit_velocity_last_90_days": 60,
        "pull_requests_opened_last_90_days": 12,
        "repositories_contributed_to": 2,
        "external_pr_ratio": 0.2,
        "code_reviews_conducted": 10,
        "review_to_pr_ratio": 0.3,
        "avg_active_repo_longevity_months": 8,
        "active_repositories_last_6_months": 3,
        "pr_merge_ratio_pct": 82.0,
        "merged_prs_count": 9,
        "closed_prs_count": 2,
        "total_recent_prs": 11,
        "top_languages": ["Python", "TypeScript", "Go"],
        "dominant_frameworks": ["fastapi", "react"],
    }
    base.update(overrides)
    return base


class ProfileScoringEngineTests(unittest.TestCase):
    def test_clear_junior_profile(self):
        result = ProfileScoringEngine(payload(
            commit_velocity_last_90_days=8,
            code_reviews_conducted=0,
            review_to_pr_ratio=0.0,
            avg_active_repo_longevity_months=1,
            active_repositories_last_6_months=1,
            pr_merge_ratio_pct=50.0,
            total_recent_prs=2,
            top_languages=["Python"],
            dominant_frameworks=[],
        )).generate_payload()
        self.assertEqual(result["seniority_estimate"], "Junior")
        self.assertEqual(result["seniority_confidence"], "Low")

    def test_clear_mid_level_profile(self):
        result = ProfileScoringEngine(payload()).generate_payload()
        self.assertEqual(result["seniority_estimate"], "Mid-Level")

    def test_clear_senior_profile(self):
        result = ProfileScoringEngine(payload(
            commit_velocity_last_90_days=140,
            code_reviews_conducted=22,
            review_to_pr_ratio=0.65,
            avg_active_repo_longevity_months=16,
            active_repositories_last_6_months=5,
            pr_merge_ratio_pct=91.0,
            repositories_contributed_to=4,
            external_pr_ratio=0.32,
        )).generate_payload()
        self.assertEqual(result["seniority_estimate"], "Senior")
        self.assertIn(result["seniority_confidence"], {"Medium", "High"})

    def test_clear_staff_profile(self):
        result = ProfileScoringEngine(payload(
            commit_velocity_last_90_days=260,
            code_reviews_conducted=55,
            review_to_pr_ratio=1.1,
            avg_active_repo_longevity_months=30,
            active_repositories_last_6_months=9,
            pr_merge_ratio_pct=95.0,
            repositories_contributed_to=6,
            external_pr_ratio=0.5,
        )).generate_payload()
        self.assertEqual(result["seniority_estimate"], "Staff")
        self.assertEqual(result["seniority_confidence"], "High")

    def test_sparse_profile_forces_low_confidence(self):
        result = ProfileScoringEngine(payload(
            commit_velocity_last_90_days=0,
            code_reviews_conducted=0,
            review_to_pr_ratio=0.0,
            avg_active_repo_longevity_months=0,
            active_repositories_last_6_months=0,
            total_recent_prs=0,
            pr_merge_ratio_pct=0.0,
        )).generate_payload()
        self.assertIsNotNone(result["seniority_estimate"])
        self.assertEqual(result["seniority_confidence"], "Low")
        self.assertIsNotNone(result["low_signal_reason"])

    def test_high_velocity_low_collaboration_profile(self):
        result = ProfileScoringEngine(payload(
            commit_velocity_last_90_days=220,
            active_repositories_last_6_months=6,
            code_reviews_conducted=1,
            review_to_pr_ratio=0.05,
            external_pr_ratio=0.02,
        )).generate_payload()
        self.assertEqual(result["execution_velocity"], "Top 10% Contributor")
        self.assertIn("low review participation", result["risk_flags"])

    def test_high_longevity_maintainer_profile(self):
        result = ProfileScoringEngine(payload(
            avg_active_repo_longevity_months=26,
            code_reviews_conducted=18,
            review_to_pr_ratio=0.55,
            pr_merge_ratio_pct=88.0,
        )).generate_payload()
        self.assertEqual(result["lifecycle_fit"], "Scale & Optimize")
        self.assertIn(result["archetype"], {"Enterprise Architect", "Deep Specialist", "Consistent Craftsman"})

    def test_high_external_contribution_profile(self):
        result = ProfileScoringEngine(payload(
            external_pr_ratio=0.58,
            repositories_contributed_to=7,
            code_reviews_conducted=20,
            review_to_pr_ratio=0.6,
        )).generate_payload()
        self.assertEqual(result["archetype"], "OSS Titan")

    def test_conflicting_profile_reduces_confidence(self):
        result = ProfileScoringEngine(payload(
            commit_velocity_last_90_days=180,
            pr_merge_ratio_pct=40.0,
            total_recent_prs=12,
            review_to_pr_ratio=0.7,
            avg_active_repo_longevity_months=2,
        )).generate_payload()
        self.assertIn(result["seniority_confidence"], {"Low", "Medium"})
        self.assertGreater(len(result["rule_trace"]), 0)


if __name__ == "__main__":
    unittest.main()

import pathlib
import sys
import unittest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from dimension_engine import DimensionScoringEngine
from domain_inference import DomainInferenceEngine
from placement_engine import PlacementEngine
from feature_engine import FeatureEngineeringEngine
from scoring_engine import ProfileScoringEngine


def payload(**overrides):
    base = {
        "name": "Test User",
        "bio": "Backend engineer",
        "company": "GitDecode",
        "location": "Remote",
        "followers": 25,
        "following": 12,
        "account_age_months": 48,
        "commit_velocity_last_90_days": 60,
        "pull_requests_opened_last_90_days": 12,
        "repositories_contributed_to": 2,
        "owned_repositories_count": 10,
        "stars_on_owned_repos": 35,
        "forks_on_owned_repos": 12,
        "pinned_repositories_count": 4,
        "pinned_languages": ["Python", "TypeScript"],
        "pinned_topics": ["backend", "api", "docker"],
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


def score_profile(**overrides):
    metrics = payload(**overrides)
    features = FeatureEngineeringEngine(metrics).generate_payload()
    dimensions = DimensionScoringEngine(metrics, features).generate_payload()
    domains = DomainInferenceEngine(metrics).generate_payload()
    scoring = ProfileScoringEngine(metrics, features, dimensions, domains).generate_payload()
    placement = PlacementEngine(metrics, scoring["dimension_scores"], domains).generate_payload()
    return scoring, placement


class ProfileScoringEngineTests(unittest.TestCase):
    def test_junior_profile(self):
        result, placement = score_profile(
            commit_velocity_last_90_days=8,
            code_reviews_conducted=0,
            review_to_pr_ratio=0.0,
            avg_active_repo_longevity_months=1,
            active_repositories_last_6_months=1,
            pr_merge_ratio_pct=50.0,
            total_recent_prs=2,
            top_languages=["Python"],
            dominant_frameworks=[],
        )
        self.assertEqual(result["seniority_estimate"], "Junior")
        self.assertGreaterEqual(len(result["engineering_signals"]), 4)
        self.assertGreaterEqual(len(placement["placement_recommendations"]), 1)

    def test_mid_level_profile(self):
        result, _ = score_profile()
        self.assertEqual(result["seniority_estimate"], "Mid-Level")
        self.assertIn("dimension_scores", result)
        self.assertIn("creator_signal", result)

    def test_senior_profile(self):
        result, _ = score_profile(
            commit_velocity_last_90_days=140,
            code_reviews_conducted=22,
            review_to_pr_ratio=0.65,
            avg_active_repo_longevity_months=16,
            active_repositories_last_6_months=5,
            pr_merge_ratio_pct=91.0,
            repositories_contributed_to=4,
            external_pr_ratio=0.32,
            stars_on_owned_repos=90,
        )
        self.assertEqual(result["seniority_estimate"], "Senior")
        self.assertGreaterEqual(result["dimension_scores"]["collaboration"], 50)

    def test_staff_profile(self):
        result, placement = score_profile(
            commit_velocity_last_90_days=260,
            code_reviews_conducted=55,
            review_to_pr_ratio=1.1,
            avg_active_repo_longevity_months=30,
            active_repositories_last_6_months=9,
            pr_merge_ratio_pct=95.0,
            repositories_contributed_to=6,
            external_pr_ratio=0.5,
            owned_repositories_count=25,
            stars_on_owned_repos=250,
        )
        self.assertEqual(result["seniority_estimate"], "Staff")
        self.assertIn("environment_fit", placement)

    def test_high_velocity_low_collaboration_profile(self):
        result, _ = score_profile(
            commit_velocity_last_90_days=220,
            active_repositories_last_6_months=6,
            code_reviews_conducted=1,
            review_to_pr_ratio=0.05,
            external_pr_ratio=0.02,
        )
        self.assertEqual(result["execution_velocity"], "Top 10% Contributor")
        self.assertIn("low review participation", result["risk_flags"])

    def test_high_longevity_maintainer_profile(self):
        result, _ = score_profile(
            avg_active_repo_longevity_months=26,
            code_reviews_conducted=18,
            review_to_pr_ratio=0.55,
            pr_merge_ratio_pct=88.0,
        )
        self.assertEqual(result["lifecycle_fit"], "Scale & Optimize")
        self.assertIn(result["archetype"], {"Enterprise Architect", "Deep Specialist", "Consistent Craftsman"})

    def test_high_external_contribution_profile(self):
        result, _ = score_profile(
            external_pr_ratio=0.58,
            repositories_contributed_to=7,
            code_reviews_conducted=20,
            review_to_pr_ratio=0.6,
        )
        self.assertEqual(result["archetype"], "OSS Titan")

    def test_domain_focus_inference(self):
        result, _ = score_profile(
            top_languages=["TypeScript", "JavaScript"],
            dominant_frameworks=["react", "nextjs"],
            pinned_topics=["frontend", "ui"],
        )
        self.assertEqual(result["domain_focus"], "Frontend")

    def test_creator_signal_uses_stars_and_contribution_breadth(self):
        result, _ = score_profile(
            stars_on_owned_repos=180,
            repositories_contributed_to=6,
        )
        self.assertEqual(result["creator_signal"]["stars_on_owned_repos"], 180)
        self.assertEqual(result["creator_signal"]["repositories_contributed_to"], 6)
        self.assertGreater(result["creator_signal"]["score"], 0)

    def test_high_impact_creator_is_not_mid_level_generalist(self):
        result, _ = score_profile(
            commit_velocity_last_90_days=752,
            pull_requests_opened_last_90_days=0,
            code_reviews_conducted=2,
            review_to_pr_ratio=0.0,
            avg_active_repo_longevity_months=69.5,
            active_repositories_last_6_months=11,
            pr_merge_ratio_pct=0.0,
            total_recent_prs=0,
            repositories_contributed_to=0,
            owned_repositories_count=11,
            stars_on_owned_repos=234148,
            followers=290303,
            external_pr_ratio=0.0,
            top_languages=["C", "C++"],
            dominant_frameworks=[],
            pinned_topics=["kernel", "systems"],
        )
        self.assertEqual(result["archetype"], "OSS Titan")
        self.assertEqual(result["seniority_estimate"], "Staff")
        self.assertNotIn("low review participation", result["risk_flags"])
        self.assertNotIn("low external collaboration", result["risk_flags"])

    def test_high_impact_public_creator_with_low_collaboration_is_not_mid_level(self):
        result, _ = score_profile(
            name="Andrej Karpathy",
            followers=125000,
            commit_velocity_last_90_days=88,
            pull_requests_opened_last_90_days=1,
            code_reviews_conducted=0,
            review_to_pr_ratio=0.0,
            avg_active_repo_longevity_months=22,
            active_repositories_last_6_months=4,
            pr_merge_ratio_pct=100.0,
            total_recent_prs=1,
            repositories_contributed_to=0,
            owned_repositories_count=12,
            stars_on_owned_repos=96000,
            external_pr_ratio=0.0,
            top_languages=["Python", "C++", "Jupyter Notebook"],
            dominant_frameworks=["pytorch"],
            pinned_topics=["machine-learning", "llm", "ai"],
        )
        self.assertEqual(result["archetype"], "OSS Titan")
        self.assertIn(result["seniority_estimate"], {"Senior", "Staff"})


if __name__ == "__main__":
    unittest.main()

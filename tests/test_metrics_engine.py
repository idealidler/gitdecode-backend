import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from metrics_engine import BehavioralMetricsEngine


def iso_days_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


class BehavioralMetricsEngineTests(unittest.TestCase):
    def test_merge_ratio_ignores_old_pull_requests(self):
        raw_payload = {
            "data": {
                "user": {
                    "name": "Test User",
                    "contributionsCollection": {
                        "totalCommitContributions": 5,
                        "totalPullRequestContributions": 0,
                        "totalPullRequestReviewContributions": 0,
                        "totalRepositoriesWithContributedPullRequests": 0,
                    },
                    "pullRequests": {
                        "nodes": [
                            {
                                "state": "MERGED",
                                "createdAt": iso_days_ago(140),
                                "repository": {"owner": {"login": "test-user"}},
                            },
                            {
                                "state": "MERGED",
                                "createdAt": iso_days_ago(160),
                                "repository": {"owner": {"login": "test-user"}},
                            },
                        ]
                    },
                    "repositories": {"nodes": []},
                }
            }
        }

        result = BehavioralMetricsEngine("test-user", raw_payload).generate_payload()

        self.assertEqual(result["pull_requests_opened_last_90_days"], 0)
        self.assertEqual(result["total_recent_prs"], 0)
        self.assertEqual(result["pr_merge_ratio_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()

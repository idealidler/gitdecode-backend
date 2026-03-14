from datetime import datetime, timedelta, timezone
from collections import Counter

class BehavioralMetricsEngine:
    def __init__(self, username: str, raw_graphql_data: dict):
        self.username = username
        
        # SAFE GET: If data is None, fallback to {}
        data_block = raw_graphql_data.get('data') or {}
        self.data = data_block.get('user') or {}

    def _safe_divide(self, numerator, denominator, round_digits=2):
        """Prevents fatal crashes if a developer has 0 PRs or 0 Repos."""
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, round_digits)

    def _calculate_months_between(self, start_str, end_str):
        """Calculates exact months between two ISO timestamps."""
        if not start_str or not end_str:
            return 0
        start = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        end = datetime.strptime(end_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return max(0, (end.year - start.year) * 12 + end.month - start.month)

    def _parse_iso_datetime(self, value):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    def _months_since(self, value):
        date_value = self._parse_iso_datetime(value)
        if not date_value:
            return 0
        now = datetime.now(timezone.utc)
        return max(0, (now.year - date_value.year) * 12 + now.month - date_value.month)

    def generate_payload(self) -> dict:
        """The main ETL pipeline that outputs the strictly formatted JSON for the LLM."""
        if not self.data:
            return {"error": "No data to process"}

        # 1. Base Collections
        contribs = self.data.get('contributionsCollection') or {}
        commits_90d = contribs.get('totalCommitContributions', 0)
        reviews = contribs.get('totalPullRequestReviewContributions', 0)
        prs_opened = contribs.get('totalPullRequestContributions', 0)
        repos_contributed_to = contribs.get('totalRepositoriesWithContributedPullRequests', 0)

        # 2. PR Analysis
        pr_nodes = (self.data.get('pullRequests') or {}).get('nodes') or []
        merged_prs = 0
        closed_prs = 0
        external_prs = 0
        recent_pr_nodes = []
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

        for pr in pr_nodes:
            if not pr: continue
            created_at = self._parse_iso_datetime(pr.get('createdAt'))
            if created_at and created_at < ninety_days_ago:
                continue

            recent_pr_nodes.append(pr)
            state = pr.get('state')
            if state == 'MERGED':
                merged_prs += 1
            elif state == 'CLOSED':
                closed_prs += 1
            
            # SAFE GET: PRs can have null repositories if the repo was deleted
            repo = pr.get('repository') or {}
            owner = repo.get('owner') or {}
            repo_owner = owner.get('login', '')
            
            if repo_owner and repo_owner.lower() != self.username.lower():
                external_prs += 1

        total_recent_prs = merged_prs + closed_prs
        
        # 3. Repository Analysis
        repo_nodes = (self.data.get('repositories') or {}).get('nodes') or []
        repo_total_count = (self.data.get('repositories') or {}).get('totalCount', 0)
        total_active_repo_months = 0
        valid_active_repos = 0
        active_last_6m = 0
        stars_on_owned_repos = 0
        forks_on_owned_repos = 0
        pinned_topics = []
        pinned_languages = []
        
        languages = []
        frameworks = []
        
        now = datetime.now(timezone.utc)

        for repo in repo_nodes:
            if not repo: continue
            
            created_at = repo.get('createdAt')
            updated_at = repo.get('updatedAt')
            stars_on_owned_repos += repo.get('stargazerCount', 0) or 0
            forks_on_owned_repos += repo.get('forkCount', 0) or 0
            
            # Check if active in the last 12 months
            is_active_recently = False
            if updated_at:
                up_date = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if (now - up_date).days <= 180:
                    active_last_6m += 1
                    is_active_recently = True

            # Calculate Longevity ONLY for actively maintained repos
            if created_at and updated_at and is_active_recently:
                months_active = self._calculate_months_between(created_at, updated_at)
                total_active_repo_months += months_active
                valid_active_repos += 1

            # SAFE GET: Primary language can be null
            lang_obj = repo.get('primaryLanguage') or {}
            lang = lang_obj.get('name')
            if lang:
                languages.append(lang)
                
            # SAFE GET: Topics can be deeply nested and contain nulls
            topics_obj = repo.get('repositoryTopics') or {}
            topics = topics_obj.get('nodes') or []
            for t in topics:
                if not t: continue
                topic_obj = t.get('topic') or {}
                topic_name = topic_obj.get('name')
                if topic_name:
                    frameworks.append(topic_name)

        pinned_nodes = (self.data.get('pinnedItems') or {}).get('nodes') or []
        for repo in pinned_nodes:
            if not repo:
                continue
            lang_obj = repo.get('primaryLanguage') or {}
            lang = lang_obj.get('name')
            if lang:
                pinned_languages.append(lang)
            topics_obj = repo.get('repositoryTopics') or {}
            topics = topics_obj.get('nodes') or []
            for t in topics:
                if not t:
                    continue
                topic_obj = t.get('topic') or {}
                topic_name = topic_obj.get('name')
                if topic_name:
                    pinned_topics.append(topic_name)

        # 4. Final Mathematical Calculations
        pr_merge_ratio_pct = self._safe_divide(merged_prs * 100, total_recent_prs, 1)
        review_to_pr_ratio = self._safe_divide(reviews, prs_opened, 2)
        external_pr_ratio = self._safe_divide(external_prs, len(recent_pr_nodes) if recent_pr_nodes else 0, 2)
        
        # New Strict Longevity Calculation
        avg_active_repo_longevity = self._safe_divide(total_active_repo_months, valid_active_repos, 1)

        # Extract the absolute most frequently used technologies
        top_languages = [item[0] for item in Counter(languages).most_common(3)]
        dominant_frameworks = [item[0] for item in Counter(frameworks).most_common(4)]

        # 5. The Structured Output Payload
        return {
            "name": self.data.get("name") or self.username,
            "bio": self.data.get("bio") or "",
            "company": self.data.get("company") or "",
            "location": self.data.get("location") or "",
            "followers": ((self.data.get("followers") or {}).get("totalCount") or 0),
            "following": ((self.data.get("following") or {}).get("totalCount") or 0),
            "account_age_months": self._months_since(self.data.get("createdAt")),
            "commit_velocity_last_90_days": commits_90d,
            "pull_requests_opened_last_90_days": prs_opened,
            "repositories_contributed_to": repos_contributed_to,
            "owned_repositories_count": repo_total_count,
            "external_pr_ratio": external_pr_ratio,
            "code_reviews_conducted": reviews,
            "review_to_pr_ratio": review_to_pr_ratio,
            "avg_active_repo_longevity_months": avg_active_repo_longevity, # <-- Updated Key
            "active_repositories_last_6_months": active_last_6m,
            "pr_merge_ratio_pct": pr_merge_ratio_pct,
            "merged_prs_count": merged_prs,
            "closed_prs_count": closed_prs,
            "total_recent_prs": total_recent_prs,
            "stars_on_owned_repos": stars_on_owned_repos,
            "forks_on_owned_repos": forks_on_owned_repos,
            "pinned_repositories_count": len(pinned_nodes),
            "pinned_languages": [item[0] for item in Counter(pinned_languages).most_common(3)],
            "pinned_topics": [item[0] for item in Counter(pinned_topics).most_common(6)],
            "top_languages": top_languages,
            "dominant_frameworks": dominant_frameworks
        }

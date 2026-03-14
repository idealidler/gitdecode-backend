from __future__ import annotations

from typing import Any, Dict, List, Tuple


class DomainInferenceEngine:
    def __init__(self, metrics_payload: Dict[str, Any]):
        self.metrics = metrics_payload

    def _build_scorecard(self) -> List[Tuple[str, int]]:
        languages = [str(item).lower() for item in self.metrics.get("top_languages", [])]
        frameworks = [str(item).lower() for item in self.metrics.get("dominant_frameworks", [])]
        pinned_topics = [str(item).lower() for item in self.metrics.get("pinned_topics", [])]
        pinned_languages = [str(item).lower() for item in self.metrics.get("pinned_languages", [])]

        signals = languages + frameworks + pinned_topics + pinned_languages

        scorecard = {
            "Backend": 0,
            "Frontend": 0,
            "Data / ML": 0,
            "Platform / Infra": 0,
            "Mobile": 0,
            "DevTools / OSS": 0,
        }

        for signal in signals:
            if signal in {"python", "go", "java", "rust", "fastapi", "django", "flask", "spring", "api", "postgres", "backend"}:
                scorecard["Backend"] += 2
            if signal in {"typescript", "javascript", "react", "nextjs", "vue", "frontend", "ui", "css", "tailwind"}:
                scorecard["Frontend"] += 2
            if signal in {"python", "jupyter", "pandas", "numpy", "tensorflow", "pytorch", "machine-learning", "data-science"}:
                scorecard["Data / ML"] += 2
            if signal in {"docker", "kubernetes", "terraform", "ansible", "devops", "aws", "gcp", "platform", "infrastructure"}:
                scorecard["Platform / Infra"] += 2
            if signal in {"swift", "objective-c", "android", "ios", "mobile", "flutter", "react-native"}:
                scorecard["Mobile"] += 2
            if signal in {"cli", "tooling", "developer-tools", "devtools", "open-source", "oss", "library"}:
                scorecard["DevTools / OSS"] += 2

        return sorted(scorecard.items(), key=lambda item: item[1], reverse=True)

    def generate_payload(self) -> Dict[str, Any]:
        ordered = self._build_scorecard()
        primary_domain = ordered[0][0] if ordered and ordered[0][1] > 0 else "Generalist Software Engineering"
        secondary_domain = ordered[1][0] if len(ordered) > 1 and ordered[1][1] > 0 else None

        return {
            "primary_domain": primary_domain,
            "secondary_domain": secondary_domain,
            "scorecard": ordered,
        }

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProjectConfig:
    name: str
    python_version: str
    app_types: list[str]                   # e.g. ["REST API", "Agent"] — multi-select
    llm_backend: str = "Azure OpenAI"
    agent_framework: str = "None — raw SDK"
    api_framework: str = "FastAPI"
    frontend: str = "None"
    frontend_tailwind: bool = True
    frontend_shadcn: bool = True
    database: str = "None — stateless"
    auth: str = "API key header"
    logging_style: str = "rotating"
    docker: bool = True
    infra: str = "Azure Container Apps — Bicep"
    environments: str = "dev,qa,prd"      # comma-separated env names
    precommit: bool = True
    git: bool = True

    # ── derived ──────────────────────────────────────────────────────────────

    @property
    def pkg_name(self) -> str:
        return self.name.lower().replace("-", "_").replace(" ", "_")

    @property
    def app_type(self) -> str:
        """Primary app type — first selected."""
        return self.app_types[0] if self.app_types else "REST API"

    @property
    def is_rest_api(self) -> bool:
        return "REST API" in self.app_types

    @property
    def is_agent(self) -> bool:
        return "Agent" in self.app_types

    @property
    def is_teams(self) -> bool:
        return "Teams Bot" in self.app_types

    @property
    def is_batch(self) -> bool:
        return "Batch / CronJob" in self.app_types

    @property
    def has_api(self) -> bool:
        return self.api_framework not in ("None", "none", "")

    @property
    def uses_azure_openai(self) -> bool:
        return self.llm_backend == "Azure OpenAI"

    @property
    def uses_maf(self) -> bool:
        return self.agent_framework == "Microsoft AF"

    @property
    def env_list(self) -> list[str]:
        return [e.strip() for e in self.environments.split(",") if e.strip()]

    @property
    def frontend_is_nextjs(self) -> bool:
        return self.frontend == "Next.js 15"

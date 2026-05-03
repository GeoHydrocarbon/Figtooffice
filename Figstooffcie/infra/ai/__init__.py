from core.config import AppSettings, SecretSettings
from infra.ai.siliconflow_provider import SiliconFlowVisionProvider


def build_provider(settings: AppSettings, secrets: SecretSettings) -> SiliconFlowVisionProvider:
    if settings.provider != "siliconflow":
        raise ValueError(f"当前只支持 siliconflow，收到：{settings.provider}")
    return SiliconFlowVisionProvider(
        api_key=secrets.api_key,
        base_url=settings.base_url,
    )

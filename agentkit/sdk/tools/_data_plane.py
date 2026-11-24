"""Route Tools data-plane actions before the shared transport signs requests."""

from agentkit.platform.provider import CloudProvider


class ToolsDataPlaneMixin:
    _DATA_ACTIONS = frozenset(
        {"AsyncExecCommand", "ViewAsyncCommand", "DeleteAsyncCommand"}
    )

    def __init__(self, *args, data_plane_host: str = "", **kwargs):
        """Optionally override the data-plane hostname (without scheme or path)."""
        if data_plane_host and any(c in data_plane_host for c in "/?#"):
            raise ValueError(
                "data_plane_host must be a hostname without scheme or path"
            )
        self.data_plane_host = data_plane_host
        super().__init__(*args, **kwargs)

    def prepare_request(self, api_info, params, doseq=0):
        request = super().prepare_request(api_info, params, doseq)
        if api_info.query.get("Action") in self._DATA_ACTIONS:
            host = self.data_plane_host
            if not host:
                if self._platform_config.provider != CloudProvider.VOLCENGINE:
                    raise ValueError(
                        "Async command APIs require an explicit data_plane_host "
                        "for this cloud provider"
                    )
                host = f"agentkit.{self.region}.volces.com"
            request.set_host(host)
            request.headers["Host"] = host
        return request

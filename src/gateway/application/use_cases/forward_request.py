from src.gateway.application.dtos.proxy_request_context import ProxyRequestContext
from src.gateway.domain.ports.route_repository import RouteRepository
from src.gateway.infrastructure.proxy.http_proxy import HttpProxy, ProxyResponse


class RouteNotFoundError(Exception):
    pass


class ForwardRequest:
    """
    Orquestra o fluxo de forwarding.
    
    Recebe o body como parâmetro separado do contexto —
    ele não é inspecionado, não influencia nenhuma decisão,
    é apenas carregado e entregue ao proxy.
    """

    def __init__(self, route_repository: RouteRepository, proxy: HttpProxy):
        self._routes = route_repository
        self._proxy = proxy

    async def execute(
        self,
        context: ProxyRequestContext,
        raw_body: bytes,
    ) -> ProxyResponse:
        route = await self._routes.get_by_tenant_slug(context.tenant_slug)

        if route is None:
            raise RouteNotFoundError(
                f"Tenant '{context.tenant_slug}' não encontrado."
            )

        upstream_url = route.build_upstream_url(context.upstream_path)

        return await self._proxy.forward(
            method=context.method,
            url=upstream_url,
            headers=context.headers,
            body=raw_body,
            query_params=context.query_params,
        )
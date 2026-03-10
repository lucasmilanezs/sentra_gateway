from src.gateway.application.dtos.proxy_request_context import ProxyRequestContext
from src.gateway.domain.ports.route_repository import RouteRepository
from src.gateway.infrastructure.proxy.http_proxy import HttpProxy, ProxyResponse


class RouteNotFoundError(Exception):
    pass


class ForwardRequest:
    """
    Orquestra o fluxo completo de forwarding:
      1. Resolve a rota pelo tenant_slug
      2. Constrói a URL upstream
      3. Encaminha e retorna a resposta

    Não sabe nada sobre FastAPI, httpx ou banco de dados.
    Depende apenas de abstrações.
    """

    def __init__(self, route_repository: RouteRepository, proxy: HttpProxy):
        self._routes = route_repository
        self._proxy = proxy

    async def execute(self, context: ProxyRequestContext) -> ProxyResponse:
        route = await self._routes.get_by_tenant_slug(context.tenant_slug)

        if route is None:
            raise RouteNotFoundError(
                f"Nenhuma rota registrada para tenant: '{context.tenant_slug}'"
            )

        upstream_url = route.build_upstream_url(context.upstream_path)

        return await self._proxy.forward(
            method=context.method,
            url=upstream_url,
            headers=context.headers,
            body=context.body,
            query_params=context.query_params,
        )
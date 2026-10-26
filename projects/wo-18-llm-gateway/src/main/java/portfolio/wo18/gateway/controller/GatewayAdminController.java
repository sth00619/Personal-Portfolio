package portfolio.wo18.gateway.controller;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
import portfolio.wo18.gateway.config.GatewayProperties.ProviderTarget;
import portfolio.wo18.gateway.contract.RatePolicy;
import portfolio.wo18.gateway.contract.UsageTotals;
import portfolio.wo18.gateway.limiter.RatePolicyStore;
import portfolio.wo18.gateway.metrics.GatewayMetrics;
import portfolio.wo18.gateway.resilience.CircuitBreakerRegistry;
import portfolio.wo18.gateway.service.ProviderRoutingService;

@RestController
@RequestMapping("/admin")
@ConditionalOnProperty(name = "app.role", havingValue = "gateway", matchIfMissing = true)
public class GatewayAdminController {
    private final RestClient client;
    private final ProviderRoutingService routing;
    private final GatewayMetrics metrics;
    private final CircuitBreakerRegistry circuits;
    private final RatePolicyStore policies;

    public GatewayAdminController(RestClient gatewayRestClient, ProviderRoutingService routing,
                                  GatewayMetrics metrics, CircuitBreakerRegistry circuits,
                                  RatePolicyStore policies) {
        this.client = gatewayRestClient;
        this.routing = routing;
        this.metrics = metrics;
        this.circuits = circuits;
        this.policies = policies;
    }

    @GetMapping("/metrics")
    public Map<String, Object> metrics() {
        return Map.of("gateway", metrics.snapshot(), "circuits", circuits.snapshots(),
                "ratePolicy", policies.current(), "routeOrder", routing.providers().stream().map(ProviderTarget::id).toList());
    }

    @GetMapping("/usage")
    public Map<String, Object> usage() {
        Map<String, UsageTotals> providers = new LinkedHashMap<>();
        long requestCount = 0L, promptTokens = 0L, completionTokens = 0L, costMicroUsd = 0L;
        for (ProviderTarget target : routing.providers()) {
            UsageTotals usage = client.get().uri(target.baseUrl() + "/internal/admin/usage")
                    .retrieve().body(UsageTotals.class);
            if (usage == null) continue;
            providers.put(target.id(), usage);
            requestCount += usage.requests();
            promptTokens += usage.promptTokens();
            completionTokens += usage.completionTokens();
            costMicroUsd += usage.costMicroUsd();
        }
        UsageTotals actual = new UsageTotals(requestCount, promptTokens, completionTokens,
                promptTokens + completionTokens, costMicroUsd);
        return Map.of("gateway", metrics.snapshot().gatewayUsage(), "providerActual", actual,
                "providers", providers,
                "exactMatch", metrics.snapshot().gatewayUsage().equals(actual));
    }

    @PostMapping("/policy")
    public Map<String, String> setPolicy(@RequestBody PolicyRequest request) {
        try {
            RatePolicy next = RatePolicy.valueOf(request.policy().toUpperCase());
            policies.set(next);
            return Map.of("policy", next.name());
        } catch (RuntimeException exception) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "policy must be QUEUE or REJECT");
        }
    }

    @PostMapping("/providers/{providerId}/mode")
    public Map<?, ?> setProviderMode(@PathVariable String providerId, @RequestBody ProviderModeRequest request) {
        ProviderTarget target = routing.providers().stream().filter(provider -> provider.id().equals(providerId))
                .findFirst().orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Unknown provider"));
        String mode = request.mode().toUpperCase();
        if (!List.of("NORMAL", "FAIL_ALL", "FAIL_NEXT", "SLOW").contains(mode)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "mode must be NORMAL, FAIL_ALL, FAIL_NEXT, or SLOW");
        }
        return client.post().uri(target.baseUrl() + "/internal/admin/config")
                .body(new ProviderConfig(mode, request.delayMs(), request.failureCount()))
                .retrieve().body(Map.class);
    }

    @PostMapping("/route-order")
    public Map<String, List<String>> setRouteOrder(@RequestBody RouteOrderRequest request) {
        try {
            return Map.of("routeOrder", routing.setOrder(request.providers()));
        } catch (IllegalArgumentException exception) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, exception.getMessage());
        }
    }

    @PostMapping("/reset")
    public Map<String, String> reset() {
        metrics.reset();
        circuits.reset();
        policies.set(RatePolicy.REJECT);
        routing.resetOrder();
        for (ProviderTarget target : routing.providers()) {
            client.post().uri(target.baseUrl() + "/internal/admin/reset").retrieve().toBodilessEntity();
        }
        return Map.of("status", "reset; use a new X-API-Key to start a fresh Redis bucket");
    }

    public record PolicyRequest(String policy) {}
    public record ProviderModeRequest(String mode, long delayMs, int failureCount) {}
    public record ProviderConfig(String mode, long delayMs, int failureCount) {}
    public record RouteOrderRequest(List<String> providers) {}
}

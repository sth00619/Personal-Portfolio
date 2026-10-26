package portfolio.wo18.gateway.service;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;
import portfolio.wo18.gateway.config.GatewayProperties;
import portfolio.wo18.gateway.config.GatewayProperties.ProviderTarget;
import portfolio.wo18.gateway.contract.ChatRequest;
import portfolio.wo18.gateway.contract.GatewayReply;
import portfolio.wo18.gateway.contract.ProviderReply;
import portfolio.wo18.gateway.metrics.GatewayMetrics;
import portfolio.wo18.gateway.resilience.CircuitBreakerRegistry;

@Service
@ConditionalOnProperty(name = "app.role", havingValue = "gateway", matchIfMissing = true)
public class ProviderRoutingService {
    private static final int MAX_ATTEMPTS_PER_PROVIDER = 2;
    private final RestClient client;
    private final CircuitBreakerRegistry circuits;
    private final GatewayMetrics metrics;
    private final List<ProviderTarget> defaultOrder;
    private final AtomicReference<List<ProviderTarget>> order;

    public ProviderRoutingService(RestClient gatewayRestClient, GatewayProperties properties,
                                  CircuitBreakerRegistry circuits, GatewayMetrics metrics) {
        this.client = gatewayRestClient;
        this.circuits = circuits;
        this.metrics = metrics;
        List<ProviderTarget> configured = properties.providerTargets();
        if (configured.size() < 2) throw new IllegalStateException("At least two mock providers are required");
        this.defaultOrder = List.copyOf(configured);
        this.order = new AtomicReference<>(defaultOrder);
    }

    public GatewayReply complete(ChatRequest request) {
        long startedAt = System.nanoTime();
        int attempts = 0;
        List<ProviderTarget> providers = order.get();
        for (int providerIndex = 0; providerIndex < providers.size(); providerIndex++) {
            ProviderTarget provider = providers.get(providerIndex);
            if (!circuits.allowCall(provider.id())) continue;
            for (int attempt = 1; attempt <= MAX_ATTEMPTS_PER_PROVIDER; attempt++) {
                attempts++;
                metrics.recordProviderAttempt();
                try {
                    ProviderReply reply = client.post()
                            .uri(provider.baseUrl() + "/internal/v1/chat/completions")
                            .body(request)
                            .retrieve()
                            .body(ProviderReply.class);
                    if (reply == null) throw new IllegalStateException("Provider returned an empty response");
                    circuits.recordSuccess(provider.id());
                    long elapsedMs = (System.nanoTime() - startedAt) / 1_000_000L;
                    metrics.recordSuccess(reply, providerIndex > 0, elapsedMs);
                    return new GatewayReply(UUID.randomUUID().toString(), reply.providerId(),
                            reply.output(), reply.usage(), attempts);
                } catch (RestClientResponseException exception) {
                    HttpStatusCode status = exception.getStatusCode();
                    boolean retryable = status.is5xxServerError();
                    if (retryable) circuits.recordFailure(provider.id());
                    if (!retryable || attempt == MAX_ATTEMPTS_PER_PROVIDER || circuits.isOpen(provider.id())) break;
                    metrics.recordRetry();
                } catch (RestClientException exception) {
                    circuits.recordFailure(provider.id());
                    if (attempt == MAX_ATTEMPTS_PER_PROVIDER || circuits.isOpen(provider.id())) break;
                    metrics.recordRetry();
                }
            }
        }
        metrics.recordFailure();
        throw new ResponseStatusException(HttpStatusCode.valueOf(503),
                "No configured provider completed this request");
    }

    public List<ProviderTarget> providers() { return order.get(); }

    public void resetOrder() { order.set(defaultOrder); }

    public List<String> setOrder(List<String> providerIds) {
        List<ProviderTarget> current = order.get();
        if (providerIds.size() != current.size() || providerIds.stream().distinct().count() != current.size()) {
            throw new IllegalArgumentException("Route order must contain every provider exactly once");
        }
        List<ProviderTarget> next = new ArrayList<>();
        for (String id : providerIds) {
            ProviderTarget target = current.stream().filter(provider -> provider.id().equals(id))
                    .findFirst().orElseThrow(() -> new IllegalArgumentException("Unknown provider: " + id));
            next.add(target);
        }
        order.set(List.copyOf(next));
        return next.stream().map(ProviderTarget::id).toList();
    }
}

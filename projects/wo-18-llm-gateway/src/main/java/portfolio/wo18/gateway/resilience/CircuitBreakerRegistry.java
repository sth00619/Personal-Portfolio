package portfolio.wo18.gateway.resilience;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import portfolio.wo18.gateway.config.GatewayProperties;

@Component
@ConditionalOnProperty(name = "app.role", havingValue = "gateway", matchIfMissing = true)
public class CircuitBreakerRegistry {
    private static final Logger log = LoggerFactory.getLogger(CircuitBreakerRegistry.class);
    private final GatewayProperties properties;
    private final ConcurrentHashMap<String, Circuit> circuits = new ConcurrentHashMap<>();

    public CircuitBreakerRegistry(GatewayProperties properties) { this.properties = properties; }

    public boolean allowCall(String providerId) {
        Circuit circuit = circuits.computeIfAbsent(providerId, ignored -> new Circuit());
        synchronized (circuit) {
            if (circuit.openUntilMs == 0L) return true;
            if (System.currentTimeMillis() < circuit.openUntilMs) return false;
            if (!circuit.halfOpenProbe.compareAndSet(false, true)) return false;
            log.info("circuit provider={} transition=HALF_OPEN", providerId);
            return true;
        }
    }

    public void recordSuccess(String providerId) {
        Circuit circuit = circuits.computeIfAbsent(providerId, ignored -> new Circuit());
        synchronized (circuit) {
            boolean wasOpen = circuit.openUntilMs > 0L || circuit.halfOpenProbe.get();
            circuit.failures = 0;
            circuit.openUntilMs = 0L;
            circuit.halfOpenProbe.set(false);
            if (wasOpen) log.info("circuit provider={} transition=CLOSED", providerId);
        }
    }

    public boolean isOpen(String providerId) {
        Circuit circuit = circuits.get(providerId);
        if (circuit == null) return false;
        synchronized (circuit) {
            return circuit.openUntilMs > System.currentTimeMillis();
        }
    }

    public void recordFailure(String providerId) {
        Circuit circuit = circuits.computeIfAbsent(providerId, ignored -> new Circuit());
        synchronized (circuit) {
            if (circuit.halfOpenProbe.get()) {
                circuit.openUntilMs = System.currentTimeMillis() + properties.getCircuitOpenMs();
                circuit.halfOpenProbe.set(false);
                log.warn("circuit provider={} transition=OPEN reason=half_open_failure", providerId);
                return;
            }
            circuit.failures++;
            if (circuit.failures >= properties.getCircuitFailureThreshold()) {
                circuit.openUntilMs = System.currentTimeMillis() + properties.getCircuitOpenMs();
                circuit.failures = 0;
                log.warn("circuit provider={} transition=OPEN consecutiveFailures={}", providerId,
                        properties.getCircuitFailureThreshold());
            }
        }
    }

    public Map<String, CircuitSnapshot> snapshots() {
        return circuits.entrySet().stream().collect(java.util.stream.Collectors.toMap(
                Map.Entry::getKey, entry -> {
                    Circuit circuit = entry.getValue();
                    synchronized (circuit) {
                        String state = circuit.halfOpenProbe.get() ? "HALF_OPEN"
                                : circuit.openUntilMs == 0L ? "CLOSED"
                                : circuit.openUntilMs > System.currentTimeMillis() ? "OPEN" : "HALF_OPEN_READY";
                        return new CircuitSnapshot(state, circuit.failures,
                                Math.max(0L, circuit.openUntilMs - System.currentTimeMillis()));
                    }
                }));
    }

    public void reset() {
        circuits.clear();
        for (GatewayProperties.ProviderTarget target : properties.providerTargets()) {
            circuits.put(target.id(), new Circuit());
        }
    }

    private static class Circuit {
        private int failures;
        private long openUntilMs;
        private final AtomicBoolean halfOpenProbe = new AtomicBoolean(false);
    }

    public record CircuitSnapshot(String state, int consecutiveFailures, long remainingOpenMs) {}
}

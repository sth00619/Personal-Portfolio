package portfolio.wo18.gateway.metrics;

import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.LongAdder;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;
import portfolio.wo18.gateway.contract.ProviderReply;
import portfolio.wo18.gateway.contract.UsageTotals;

@Service
@ConditionalOnProperty(name = "app.role", havingValue = "gateway", matchIfMissing = true)
public class GatewayMetrics {
    private final LongAdder completed = new LongAdder();
    private final LongAdder failed = new LongAdder();
    private final LongAdder failovers = new LongAdder();
    private final LongAdder retries = new LongAdder();
    private final LongAdder providerAttempts = new LongAdder();
    private final LongAdder promptTokens = new LongAdder();
    private final LongAdder completionTokens = new LongAdder();
    private final LongAdder costMicroUsd = new LongAdder();
    private final LongAdder failoverLatencyMs = new LongAdder();
    private final AtomicLong firstFailoverLatencyMs = new AtomicLong(-1L);

    public void recordProviderAttempt() { providerAttempts.increment(); }
    public void recordRetry() { retries.increment(); }
    public void recordSuccess(ProviderReply reply, boolean didFailover, long elapsedMs) {
        completed.increment();
        promptTokens.add(reply.usage().promptTokens());
        completionTokens.add(reply.usage().completionTokens());
        costMicroUsd.add(reply.usage().costMicroUsd());
        if (didFailover) {
            failovers.increment();
            failoverLatencyMs.add(elapsedMs);
            firstFailoverLatencyMs.compareAndSet(-1L, elapsedMs);
        }
    }
    public void recordFailure() { failed.increment(); }

    public Snapshot snapshot() {
        long prompt = promptTokens.sum();
        long completion = completionTokens.sum();
        return new Snapshot(completed.sum(), failed.sum(), failovers.sum(), retries.sum(),
                providerAttempts.sum(), firstFailoverLatencyMs.get(), failoverLatencyMs.sum(),
                new UsageTotals(completed.sum(), prompt, completion, prompt + completion, costMicroUsd.sum()));
    }

    public void reset() {
        completed.reset(); failed.reset(); failovers.reset(); retries.reset(); providerAttempts.reset();
        promptTokens.reset(); completionTokens.reset(); costMicroUsd.reset(); failoverLatencyMs.reset();
        firstFailoverLatencyMs.set(-1L);
    }

    public record Snapshot(long completedRequests, long failedRequests, long failoverRequests,
                           long retryAttempts, long providerAttempts,
                           long firstFailoverLatencyMs, long totalFailoverLatencyMs,
                           UsageTotals gatewayUsage) {}
}

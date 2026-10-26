package portfolio.wo18.gateway.provider;

import java.util.concurrent.atomic.LongAdder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;
import portfolio.wo18.gateway.contract.ChatRequest;
import portfolio.wo18.gateway.contract.ProviderReply;
import portfolio.wo18.gateway.contract.TokenUsage;
import portfolio.wo18.gateway.contract.UsageTotals;

@Service
@ConditionalOnProperty(name = "app.role", havingValue = "provider")
public class MockProviderService {
    private static final int CHARACTERS_PER_PROMPT_TOKEN = 4;
    private static final long MOCK_COMPLETION_TOKENS = 16L;
    private static final long SLOW_MODE_MIN_DELAY_MS = 600L;
    private final String providerId;
    private final String initialMode;
    private final long initialDelayMs;
    private final int initialFailureCount;
    private volatile String mode;
    private volatile long delayMs;
    private volatile int failuresRemaining;
    private final LongAdder requests = new LongAdder();
    private final LongAdder promptTokens = new LongAdder();
    private final LongAdder completionTokens = new LongAdder();
    private final LongAdder costMicroUsd = new LongAdder();

    public MockProviderService(@Value("${mock-provider.id}") String providerId,
                               @Value("${mock-provider.mode}") String mode,
                               @Value("${mock-provider.delay-ms}") long delayMs,
                               @Value("${mock-provider.failure-count}") int failuresRemaining) {
        this.providerId = providerId;
        this.initialMode = mode.toUpperCase();
        this.initialDelayMs = delayMs;
        this.initialFailureCount = failuresRemaining;
        this.mode = mode.toUpperCase();
        this.delayMs = delayMs;
        this.failuresRemaining = failuresRemaining;
    }

    public ProviderReply complete(ChatRequest request) {
        if (shouldFail()) throw new ProviderUnavailableException("mock provider " + providerId + " returned 503");
        long delay = delayMs;
        if (mode.equals("SLOW")) delay = Math.max(delay, SLOW_MODE_MIN_DELAY_MS);
        pause(delay);
        long prompt = Math.max(1L, (request.prompt().length() + CHARACTERS_PER_PROMPT_TOKEN - 1L)
                / CHARACTERS_PER_PROMPT_TOKEN);
        TokenUsage usage = TokenUsage.of(prompt, MOCK_COMPLETION_TOKENS);
        requests.increment();
        promptTokens.add(usage.promptTokens());
        completionTokens.add(usage.completionTokens());
        costMicroUsd.add(usage.costMicroUsd());
        return new ProviderReply(providerId, "mock response from " + providerId + " for: " + request.prompt(), usage);
    }

    private boolean shouldFail() {
        String current = mode;
        if (current.equals("FAIL_ALL")) return true;
        if (current.equals("FAIL_NEXT")) {
            synchronized (this) {
                if (failuresRemaining > 0) {
                    failuresRemaining--;
                    return true;
                }
                mode = "NORMAL";
            }
        }
        return false;
    }

    private void pause(long millis) {
        if (millis <= 0) return;
        try {
            Thread.sleep(millis);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new ProviderUnavailableException("mock provider request interrupted");
        }
    }

    public synchronized void configure(String newMode, long newDelayMs, int newFailureCount) {
        this.mode = newMode.toUpperCase();
        this.delayMs = Math.max(0L, newDelayMs);
        this.failuresRemaining = Math.max(0, newFailureCount);
    }

    public UsageTotals totals() {
        long prompt = promptTokens.sum();
        long completion = completionTokens.sum();
        return new UsageTotals(requests.sum(), prompt, completion, prompt + completion, costMicroUsd.sum());
    }

    public void reset() {
        requests.reset();
        promptTokens.reset();
        completionTokens.reset();
        costMicroUsd.reset();
        configure(initialMode, initialDelayMs, initialFailureCount);
    }

    public String providerId() { return providerId; }
    public String mode() { return mode; }

    public static class ProviderUnavailableException extends RuntimeException {
        public ProviderUnavailableException(String message) { super(message); }
    }
}

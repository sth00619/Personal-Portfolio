package portfolio.wo18.gateway.limiter;

import java.util.concurrent.atomic.AtomicReference;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import portfolio.wo18.gateway.contract.RatePolicy;

@Component
@ConditionalOnProperty(name = "app.role", havingValue = "gateway", matchIfMissing = true)
public class RatePolicyStore {
    private final AtomicReference<RatePolicy> policy = new AtomicReference<>(RatePolicy.REJECT);
    public RatePolicy current() { return policy.get(); }
    public RatePolicy set(RatePolicy next) { policy.set(next); return next; }
}

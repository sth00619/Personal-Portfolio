package portfolio.wo18.gateway.controller;

import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.server.ResponseStatusException;
import jakarta.validation.Valid;
import portfolio.wo18.gateway.contract.ChatRequest;
import portfolio.wo18.gateway.contract.GatewayReply;
import portfolio.wo18.gateway.contract.RatePolicy;
import portfolio.wo18.gateway.limiter.RatePolicyStore;
import portfolio.wo18.gateway.limiter.TokenBucketRateLimiter;
import portfolio.wo18.gateway.service.ProviderRoutingService;

@RestController
@Validated
@RequestMapping("/v1")
@ConditionalOnProperty(name = "app.role", havingValue = "gateway", matchIfMissing = true)
public class GatewayController {
    private final TokenBucketRateLimiter limiter;
    private final RatePolicyStore policies;
    private final ProviderRoutingService routing;

    public GatewayController(TokenBucketRateLimiter limiter, RatePolicyStore policies,
                             ProviderRoutingService routing) {
        this.limiter = limiter;
        this.policies = policies;
        this.routing = routing;
    }

    @PostMapping("/chat/completions")
    public ResponseEntity<?> complete(@Valid @RequestBody ChatRequest request,
                                      @RequestHeader(name = "X-API-Key", defaultValue = "portfolio-demo") String apiKey) {
        if (apiKey.isBlank() || apiKey.length() > 120) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "X-API-Key must contain 1 to 120 characters");
        }
        TokenBucketRateLimiter.Decision decision = limiter.acquire(apiKey, policies.current());
        if (!decision.allowed()) {
            return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                    .header(HttpHeaders.RETRY_AFTER, "1")
                    .body(Map.of("error", "rate limit exceeded", "waitedMs", decision.waitedMs()));
        }
        GatewayReply reply = routing.complete(request);
        return ResponseEntity.ok(reply);
    }
}

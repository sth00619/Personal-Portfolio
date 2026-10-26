package portfolio.wo18.gateway.provider;

import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import portfolio.wo18.gateway.contract.ChatRequest;
import portfolio.wo18.gateway.contract.ProviderReply;
import portfolio.wo18.gateway.contract.UsageTotals;
import portfolio.wo18.gateway.provider.MockProviderService.ProviderUnavailableException;

@RestController
@RequestMapping("/internal")
@ConditionalOnProperty(name = "app.role", havingValue = "provider")
public class MockProviderController {
    private final MockProviderService provider;

    public MockProviderController(MockProviderService provider) { this.provider = provider; }

    @PostMapping("/v1/chat/completions")
    public ResponseEntity<ProviderReply> complete(@RequestBody ChatRequest request) {
        try {
            return ResponseEntity.ok(provider.complete(request));
        } catch (ProviderUnavailableException exception) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).build();
        }
    }

    @PostMapping("/admin/config")
    public Map<String, String> configure(@RequestBody ProviderConfig config) {
        provider.configure(config.mode(), config.delayMs(), config.failureCount());
        return Map.of("providerId", provider.providerId(), "mode", provider.mode());
    }

    @GetMapping("/admin/usage")
    public UsageTotals usage() { return provider.totals(); }

    @PostMapping("/admin/reset")
    public Map<String, String> reset() {
        provider.reset();
        return Map.of("status", "reset");
    }

    public record ProviderConfig(String mode, long delayMs, int failureCount) {}
}

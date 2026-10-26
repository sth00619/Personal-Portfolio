package portfolio.wo18.gateway.provider;

import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import portfolio.wo18.gateway.provider.MockProviderService.ProviderUnavailableException;

@RestControllerAdvice
@ConditionalOnProperty(name = "app.role", havingValue = "provider")
public class ProviderExceptionHandler {
    @ExceptionHandler(ProviderUnavailableException.class)
    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    public Map<String, String> unavailable(ProviderUnavailableException exception) {
        return Map.of("error", exception.getMessage());
    }
}

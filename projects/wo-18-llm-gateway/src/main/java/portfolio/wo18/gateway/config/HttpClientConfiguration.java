package portfolio.wo18.gateway.config;

import java.time.Duration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration
@ConditionalOnProperty(name = "app.role", havingValue = "gateway", matchIfMissing = true)
public class HttpClientConfiguration {
    @Bean
    public RestClient gatewayRestClient(RestClient.Builder builder, GatewayProperties properties) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Duration.ofMillis(properties.getReadTimeoutMs()));
        requestFactory.setReadTimeout(Duration.ofMillis(properties.getReadTimeoutMs()));
        return builder.requestFactory(requestFactory).build();
    }
}

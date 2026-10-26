package portfolio.wo18.gateway.contract;

public record GatewayReply(String requestId, String providerId, String output,
                           TokenUsage usage, int providerAttempts) {}

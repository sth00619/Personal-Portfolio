package portfolio.wo18.gateway.contract;

public record TokenUsage(long promptTokens, long completionTokens, long totalTokens,
                         long costMicroUsd) {
    private static final long INPUT_COST_MICRO_USD_PER_TOKEN = 2L;
    private static final long OUTPUT_COST_MICRO_USD_PER_TOKEN = 8L;

    public static TokenUsage of(long promptTokens, long completionTokens) {
        long cost = (promptTokens * INPUT_COST_MICRO_USD_PER_TOKEN)
                + (completionTokens * OUTPUT_COST_MICRO_USD_PER_TOKEN);
        return new TokenUsage(promptTokens, completionTokens,
                promptTokens + completionTokens, cost);
    }
}

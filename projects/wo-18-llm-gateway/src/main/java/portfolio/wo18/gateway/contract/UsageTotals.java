package portfolio.wo18.gateway.contract;

public record UsageTotals(long requests, long promptTokens, long completionTokens,
                          long totalTokens, long costMicroUsd) {
    public static UsageTotals empty() { return new UsageTotals(0, 0, 0, 0, 0); }
}

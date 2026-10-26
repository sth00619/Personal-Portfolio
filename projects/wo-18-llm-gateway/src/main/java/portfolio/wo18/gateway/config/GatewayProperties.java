package portfolio.wo18.gateway.config;

import java.util.ArrayList;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "gateway")
public class GatewayProperties {
    private String providerDefinitions;
    private int bucketCapacity;
    private double refillPerSecond;
    private long queueTimeoutMs;
    private int readTimeoutMs;
    private int circuitFailureThreshold;
    private long circuitOpenMs;

    public String getProviderDefinitions() { return providerDefinitions; }
    public void setProviderDefinitions(String providerDefinitions) { this.providerDefinitions = providerDefinitions; }
    public int getBucketCapacity() { return bucketCapacity; }
    public void setBucketCapacity(int bucketCapacity) { this.bucketCapacity = bucketCapacity; }
    public double getRefillPerSecond() { return refillPerSecond; }
    public void setRefillPerSecond(double refillPerSecond) { this.refillPerSecond = refillPerSecond; }
    public long getQueueTimeoutMs() { return queueTimeoutMs; }
    public void setQueueTimeoutMs(long queueTimeoutMs) { this.queueTimeoutMs = queueTimeoutMs; }
    public int getReadTimeoutMs() { return readTimeoutMs; }
    public void setReadTimeoutMs(int readTimeoutMs) { this.readTimeoutMs = readTimeoutMs; }
    public int getCircuitFailureThreshold() { return circuitFailureThreshold; }
    public void setCircuitFailureThreshold(int circuitFailureThreshold) { this.circuitFailureThreshold = circuitFailureThreshold; }
    public long getCircuitOpenMs() { return circuitOpenMs; }
    public void setCircuitOpenMs(long circuitOpenMs) { this.circuitOpenMs = circuitOpenMs; }

    public List<ProviderTarget> providerTargets() {
        List<ProviderTarget> targets = new ArrayList<>();
        if (providerDefinitions == null || providerDefinitions.isBlank()) return targets;
        for (String definition : providerDefinitions.split(",")) {
            String[] parts = definition.trim().split("=", 2);
            if (parts.length != 2 || parts[0].isBlank() || parts[1].isBlank()) {
                throw new IllegalStateException("Invalid gateway.provider-definitions entry: " + definition);
            }
            targets.add(new ProviderTarget(parts[0].trim(), parts[1].trim()));
        }
        return targets;
    }

    public record ProviderTarget(String id, String baseUrl) {}
}

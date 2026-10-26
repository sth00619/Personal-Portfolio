package portfolio.wo18.gateway.limiter;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Service;
import portfolio.wo18.gateway.config.GatewayProperties;
import portfolio.wo18.gateway.contract.RatePolicy;

@Service
@ConditionalOnProperty(name = "app.role", havingValue = "gateway", matchIfMissing = true)
public class TokenBucketRateLimiter {
    private static final long POLL_INTERVAL_MS = 10L;
    private static final long QUEUE_KEY_TTL_MS = 30_000L;
    private static final String BUCKET_SCRIPT = """
            local capacity = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local clock = redis.call('TIME')
            local now_ms = (tonumber(clock[1]) * 1000) + math.floor(tonumber(clock[2]) / 1000)
            local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens')) or capacity
            local last_ms = tonumber(redis.call('HGET', KEYS[1], 'timestamp')) or now_ms
            tokens = math.min(capacity, tokens + ((now_ms - last_ms) / 1000 * refill_rate))
            if tokens >= 1 then
              redis.call('HSET', KEYS[1], 'tokens', tokens - 1, 'timestamp', now_ms)
              redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / refill_rate * 3000))
              return 0
            end
            local wait_ms = math.ceil((1 - tokens) / refill_rate * 1000)
            redis.call('HSET', KEYS[1], 'tokens', tokens, 'timestamp', now_ms)
            redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / refill_rate * 3000))
            return wait_ms
            """;
    private static final String FIFO_BUCKET_SCRIPT = """
            local ticket = ARGV[1]
            if redis.call('LINDEX', KEYS[2], 0) ~= ticket then return -1 end
            local capacity = tonumber(ARGV[2])
            local refill_rate = tonumber(ARGV[3])
            local clock = redis.call('TIME')
            local now_ms = (tonumber(clock[1]) * 1000) + math.floor(tonumber(clock[2]) / 1000)
            local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens')) or capacity
            local last_ms = tonumber(redis.call('HGET', KEYS[1], 'timestamp')) or now_ms
            tokens = math.min(capacity, tokens + ((now_ms - last_ms) / 1000 * refill_rate))
            if tokens >= 1 then
              redis.call('HSET', KEYS[1], 'tokens', tokens - 1, 'timestamp', now_ms)
              redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / refill_rate * 3000))
              redis.call('LPOP', KEYS[2])
              redis.call('PEXPIRE', KEYS[2], 30000)
              return 0
            end
            local wait_ms = math.ceil((1 - tokens) / refill_rate * 1000)
            redis.call('HSET', KEYS[1], 'tokens', tokens, 'timestamp', now_ms)
            redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / refill_rate * 3000))
            return wait_ms
            """;
    private static final String ENQUEUE_SCRIPT = """
            local position = redis.call('RPUSH', KEYS[1], ARGV[1])
            redis.call('PEXPIRE', KEYS[1], ARGV[2])
            return position
            """;

    private final StringRedisTemplate redis;
    private final GatewayProperties properties;
    private final DefaultRedisScript<Long> bucketScript;
    private final DefaultRedisScript<Long> fifoBucketScript;
    private final DefaultRedisScript<Long> enqueueScript;

    public TokenBucketRateLimiter(StringRedisTemplate redis, GatewayProperties properties) {
        this.redis = redis;
        this.properties = properties;
        this.bucketScript = new DefaultRedisScript<>(BUCKET_SCRIPT, Long.class);
        this.fifoBucketScript = new DefaultRedisScript<>(FIFO_BUCKET_SCRIPT, Long.class);
        this.enqueueScript = new DefaultRedisScript<>(ENQUEUE_SCRIPT, Long.class);
    }

    public Decision acquire(String apiKey, RatePolicy policy) {
        String bucketKey = "wo18:rate:" + hashedKey(apiKey);
        if (policy == RatePolicy.QUEUE) return acquireFifo(apiKey, bucketKey);
        Long waitMs = redis.execute(bucketScript, List.of(bucketKey),
                Integer.toString(properties.getBucketCapacity()),
                Double.toString(properties.getRefillPerSecond()));
        if (waitMs == null) throw new IllegalStateException("Redis token bucket returned no decision");
        return new Decision(waitMs == 0L, 0L);
    }

    private Decision acquireFifo(String apiKey, String bucketKey) {
        String queueKey = "wo18:queue:" + hashedKey(apiKey);
        String ticket = UUID.randomUUID().toString();
        Long position = redis.execute(enqueueScript, List.of(queueKey), ticket,
                Long.toString(QUEUE_KEY_TTL_MS));
        if (position == null) throw new IllegalStateException("Redis FIFO queue did not accept a ticket");
        long started = System.nanoTime();
        long deadline = started + (properties.getQueueTimeoutMs() * 1_000_000L);
        boolean granted = false;
        try {
            while (true) {
                if (System.nanoTime() >= deadline) {
                    return new Decision(false, (System.nanoTime() - started) / 1_000_000L);
                }
                Long waitMs = redis.execute(fifoBucketScript, List.of(bucketKey, queueKey), ticket,
                        Integer.toString(properties.getBucketCapacity()),
                        Double.toString(properties.getRefillPerSecond()));
                if (waitMs == null) throw new IllegalStateException("Redis FIFO token bucket returned no decision");
                if (waitMs == 0L) {
                    granted = true;
                    return new Decision(true, (System.nanoTime() - started) / 1_000_000L);
                }
                long sleepMs = waitMs < 0L ? POLL_INTERVAL_MS : Math.max(1L, Math.min(POLL_INTERVAL_MS, waitMs));
                try {
                    Thread.sleep(sleepMs);
                } catch (InterruptedException exception) {
                    Thread.currentThread().interrupt();
                    return new Decision(false, (System.nanoTime() - started) / 1_000_000L);
                }
            }
        } finally {
            if (!granted) redis.opsForList().remove(queueKey, 1L, ticket);
        }
    }

    private String hashedKey(String apiKey) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(apiKey.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is required by the Java runtime", exception);
        }
    }

    public record Decision(boolean allowed, long waitedMs) {}
}

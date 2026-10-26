package portfolio.wo18.gateway.contract;

import jakarta.validation.constraints.NotBlank;

public record ChatRequest(@NotBlank String prompt, String model) {}

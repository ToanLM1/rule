package brp.codegen;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

class MainTest {
  private final ObjectMapper mapper = new ObjectMapper();
  private final JavaDecisionGenerator generator = new JavaDecisionGenerator();

  @Test
  void generationIsByteDeterministicAndCoversConformanceShapes() throws Exception {
    for (String fixture :
        new String[] {"enrollment_eligibility", "premium_adjustments", "required_documents"}) {
      JsonNode content =
          mapper.readTree(
              Path.of("../../platform/tests/fixtures/conformance/" + fixture + ".json").toFile());
      String first = generator.generate(content, "brp.rules.generated", 7, "a".repeat(64));
      String second = generator.generate(content, "brp.rules.generated", 7, "a".repeat(64));
      assertEquals(first, second);
      assertTrue(first.contains("Do not edit"));
      assertTrue(first.contains("class Output"));
      assertTrue(first.contains("LookupProvider"));
    }
  }

  @Test
  void emittedOperatorsAndPoliciesUseCentralRuntimeSemantics() throws Exception {
    JsonNode eligibility =
        mapper.readTree(
            Path.of("../../platform/tests/fixtures/conformance/enrollment_eligibility.json")
                .toFile());
    String source = generator.generate(eligibility, "brp.rules.generated", 1, "b".repeat(64));
    assertTrue(source.contains("RuleSupport.compare"));
    assertTrue(source.contains("RuleSupport.eq"));
    assertTrue(source.contains("lookup.lookup"));

    JsonNode collect =
        mapper.readTree(
            Path.of("../../platform/tests/fixtures/conformance/premium_adjustments.json").toFile());
    assertTrue(
        generator
            .generate(collect, "brp.rules.generated", 1, "c".repeat(64))
            .contains("List.copyOf(matches)"));
  }
}

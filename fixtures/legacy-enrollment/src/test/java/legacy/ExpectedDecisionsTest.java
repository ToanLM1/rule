package legacy;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

class ExpectedDecisionsTest {
  @Test
  void classifiesExactlySixLegacyConstructs() throws IOException {
    Path mapping = Path.of("expected-decisions.yaml");
    try (InputStream input = Files.newInputStream(mapping)) {
      Map<String, Object> document = new Yaml().load(input);
      List<Map<String, Object>> constructs = castList(document.get("constructs"));
      assertEquals(6, constructs.size());
      assertTrue(constructs.stream().allMatch(item -> Boolean.TRUE.equals(item.get("classified"))));
      Set<Object> ids = new HashSet<>();
      constructs.forEach(item -> ids.add(item.get("id")));
      assertEquals(6, ids.size());
    }
  }

  @SuppressWarnings("unchecked")
  private static List<Map<String, Object>> castList(Object value) {
    return (List<Map<String, Object>>) value;
  }
}

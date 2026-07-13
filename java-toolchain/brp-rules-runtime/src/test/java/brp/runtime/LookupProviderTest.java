package brp.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Map;
import org.junit.jupiter.api.Test;

class LookupProviderTest {
  @Test
  void supportsTypedLookupMaps() {
    LookupProvider provider = (name, keys) -> Map.of("eligible", true);
    assertEquals(true, provider.lookup("regions", Map.of("code", "서울")).get("eligible"));
  }
}

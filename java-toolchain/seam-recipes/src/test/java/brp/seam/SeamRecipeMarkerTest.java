package brp.seam;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class SeamRecipeMarkerTest {
  @Test
  void exposesModuleName() {
    assertEquals("brp-seam-recipes", SeamRecipeMarker.name());
  }
}

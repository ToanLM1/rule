package brp.codegen;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;

import org.junit.jupiter.api.Test;

class MainTest {
  @Test
  void mainStarts() {
    assertDoesNotThrow(() -> Main.main(new String[0]));
  }
}

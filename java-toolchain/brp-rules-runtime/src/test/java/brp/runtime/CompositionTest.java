package brp.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import java.sql.DriverManager;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class CompositionTest {
  @Test
  void restrictedAggregatorsPreserveOrderAndKorean() {
    assertEquals(new BigDecimal("50"), Composition.sum(List.of(20, 30)));
    assertEquals(List.of("건강진단서", "신분증"), Composition.distinct(List.of("건강진단서", "건강진단서", "신분증")));
    assertEquals("서울", Composition.firstNonNull(null, "서울", "부산"));
  }

  @Test
  void jdbcProviderHandlesHitMissTypeAndIdentifierSafety() throws Exception {
    try (var connection = DriverManager.getConnection("jdbc:h2:mem:lookup;MODE=PostgreSQL")) {
      connection
          .createStatement()
          .execute(
              "CREATE TABLE \"region_eligibility\"(\"region_code\" VARCHAR PRIMARY KEY, \"eligible\" BOOLEAN)");
      connection
          .createStatement()
          .execute("INSERT INTO \"region_eligibility\" VALUES ('SEOUL', TRUE)");
      var provider =
          new JdbcLookupProvider(
              connection,
              Map.of(
                  "regionEligibility",
                  new JdbcLookupProvider.Definition(
                      "region_eligibility", List.of("region_code"), List.of("eligible"))));
      assertEquals(
          true,
          provider.require(
              "regionEligibility", Map.of("region_code", "SEOUL"), "eligible", Boolean.class));
      assertThrows(
          MissingLookupException.class,
          () ->
              provider.require(
                  "regionEligibility", Map.of("region_code", "JEJU"), "eligible", Boolean.class));
      assertThrows(
          LookupTypeException.class,
          () ->
              provider.require(
                  "regionEligibility", Map.of("region_code", "SEOUL"), "eligible", String.class));
      assertThrows(
          IllegalArgumentException.class,
          () ->
              new JdbcLookupProvider(
                  connection,
                  Map.of(
                      "bad",
                      new JdbcLookupProvider.Definition(
                          "table;drop", List.of("id"), List.of("value")))));
    }
  }
}

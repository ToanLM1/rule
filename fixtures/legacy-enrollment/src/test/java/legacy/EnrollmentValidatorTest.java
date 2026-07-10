package legacy;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.List;
import legacy.model.EnrollmentRequest;
import legacy.model.EnrollmentResult;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class EnrollmentValidatorTest {
  private final EnrollmentValidator validator = new EnrollmentValidator();
  private Connection connection;

  @BeforeEach
  void createDatabase() throws SQLException {
    connection = DriverManager.getConnection("jdbc:h2:mem:enrollment;MODE=PostgreSQL");
    connection
        .createStatement()
        .execute(
            "CREATE TABLE region_eligibility "
                + "(region_code VARCHAR(32) PRIMARY KEY, region_name_kr VARCHAR(100), "
                + "eligible BOOLEAN NOT NULL)");
    connection
        .createStatement()
        .execute(
            "INSERT INTO region_eligibility VALUES "
                + "('SEOUL','서울',TRUE),('BUSAN','부산',TRUE),('JEJU','제주',FALSE)");
  }

  @AfterEach
  void closeDatabase() throws SQLException {
    connection.close();
  }

  @Test
  void rejectsUnderAge() throws SQLException {
    assertRejected(request(17, "CANCER_BASIC", false, "SEOUL", 1), "UNDER_AGE");
  }

  @Test
  void rejectsCancerApplicantOverLimit() throws SQLException {
    assertRejected(request(66, "CANCER_BASIC", false, "SEOUL", 1), "OVER_AGE_LIMIT");
  }

  @Test
  void addsSmokerLoadingForCancerProduct() throws SQLException {
    EnrollmentResult result = evaluate(request(40, "CANCER_BASIC", true, "SEOUL", 1));
    assertTrue(result.eligible());
    assertEquals(20, result.premiumLoadingPct());
  }

  @Test
  void leavesNonSmokerLoadingAtZero() throws SQLException {
    EnrollmentResult result = evaluate(request(40, "CANCER_BASIC", false, "SEOUL", 1));
    assertEquals(0, result.premiumLoadingPct());
  }

  @Test
  void rejectsIneligibleRegion() throws SQLException {
    assertRejected(request(40, "CANCER_BASIC", false, "JEJU", 1), "REGION_NOT_COVERED");
  }

  @Test
  void rejectsUnknownRegion() throws SQLException {
    assertRejected(request(40, "CANCER_BASIC", false, "UNKNOWN", 1), "REGION_NOT_COVERED");
  }

  @Test
  void requiresDocumentForOccupationClassFour() throws SQLException {
    EnrollmentResult result = evaluate(request(40, "CANCER_BASIC", false, "SEOUL", 4));
    assertEquals(List.of("DOC_HEALTH_CHECK"), result.requiredDocs());
  }

  @Test
  void requiresDocumentForOccupationClassFive() throws SQLException {
    EnrollmentResult result = evaluate(request(40, "CANCER_BASIC", false, "SEOUL", 5));
    assertEquals(List.of("DOC_HEALTH_CHECK"), result.requiredDocs());
  }

  @Test
  void addsSeniorLoadingAndDocument() throws SQLException {
    EnrollmentResult result = evaluate(request(62, "CANCER_BASIC", false, "SEOUL", 1));
    assertEquals(30, result.premiumLoadingPct());
    assertEquals(List.of("DOC_HEALTH_CHECK"), result.requiredDocs());
  }

  @Test
  void combinesSmokerAndSeniorLoading() throws SQLException {
    EnrollmentResult result = evaluate(request(62, "CANCER_BASIC", true, "SEOUL", 4));
    assertEquals(50, result.premiumLoadingPct());
    assertEquals(List.of("DOC_HEALTH_CHECK"), result.requiredDocs());
  }

  @Test
  void savingsProductDoesNotUseCancerAdjustments() throws SQLException {
    EnrollmentResult result = evaluate(request(70, "SAVINGS_PLUS", true, "BUSAN", 1));
    assertTrue(result.eligible());
    assertEquals(0, result.premiumLoadingPct());
  }

  @Test
  void ageEighteenIsEligibleBeforeRuleEdit() throws SQLException {
    EnrollmentResult result = evaluate(request(18, "CANCER_BASIC", false, "SEOUL", 1));
    assertTrue(result.eligible());
    assertEquals("ELIGIBLE", result.reasonCode());
  }

  private EnrollmentResult evaluate(EnrollmentRequest request) throws SQLException {
    return validator.evaluate(request, connection);
  }

  private void assertRejected(EnrollmentRequest request, String reason) throws SQLException {
    EnrollmentResult result = evaluate(request);
    assertFalse(result.eligible());
    assertEquals(reason, result.reasonCode());
  }

  private static EnrollmentRequest request(
      int age, String product, boolean smoker, String region, int occupation) {
    return new EnrollmentRequest(age, product, smoker, region, occupation);
  }
}

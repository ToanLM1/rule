package legacy;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import legacy.model.EnrollmentRequest;
import legacy.model.EnrollmentResult;

/** Deliberately branch-heavy legacy enrollment logic used by the mining fixture. */
public final class EnrollmentValidator {
  public EnrollmentResult evaluate(EnrollmentRequest request, Connection connection)
      throws SQLException {
    EnrollmentResult result = new EnrollmentResult();

    if (request.age() < 18) {
      result.reject("UNDER_AGE");
      return result;
    }

    if ("CANCER_BASIC".equals(request.productCode()) && request.age() > 65) {
      result.reject("OVER_AGE_LIMIT");
      return result;
    }

    if (request.smoker() && request.productCode().startsWith("CANCER")) {
      result.addPremiumLoading(20);
    }

    if (!isRegionCovered(request.regionCode(), connection)) {
      result.reject("REGION_NOT_COVERED");
      return result;
    }

    switch (request.occupationClass()) {
      case 4, 5 -> result.addRequiredDoc("DOC_HEALTH_CHECK");
      default -> {
        // No occupation document requirement.
      }
    }

    if (request.age() >= 60
        && request.age() <= 65
        && "CANCER_BASIC".equals(request.productCode())) {
      result.addPremiumLoading(30);
      result.addRequiredDoc("DOC_HEALTH_CHECK");
    }

    return result;
  }

  private boolean isRegionCovered(String regionCode, Connection connection) throws SQLException {
    String sql = "SELECT eligible FROM region_eligibility WHERE region_code = ?";
    try (PreparedStatement statement = connection.prepareStatement(sql)) {
      statement.setString(1, regionCode);
      try (ResultSet rows = statement.executeQuery()) {
        return rows.next() && rows.getBoolean("eligible");
      }
    }
  }
}

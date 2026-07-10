package legacy.model;

public record EnrollmentRequest(
    int age, String productCode, boolean smoker, String regionCode, int occupationClass) {}

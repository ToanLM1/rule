package legacy;

/** Planted class that must not be reachable from the enrollment entry point. */
public final class UnrelatedUtil {
  private UnrelatedUtil() {}

  public static boolean unrelatedDecision(int value) {
    return value > 100;
  }
}

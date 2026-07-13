package brp.runtime;

import java.math.BigDecimal;
import java.util.Collection;
import java.util.Objects;

/** Cross-generated-class implementations of the restricted IR operators. */
public final class RuleSupport {
  private RuleSupport() {}

  public static boolean eq(Object left, Object right) {
    if (left instanceof Number && right instanceof Number) {
      return decimal(left).compareTo(decimal(right)) == 0;
    }
    return Objects.equals(left, right);
  }

  public static int compare(Object left, Object right) {
    if (left instanceof Number && right instanceof Number) {
      return decimal(left).compareTo(decimal(right));
    }
    @SuppressWarnings("unchecked")
    Comparable<Object> comparable = (Comparable<Object>) left;
    return comparable.compareTo(right);
  }

  public static boolean contains(Collection<?> values, Object value) {
    return values.stream().anyMatch(item -> eq(item, value));
  }

  public static boolean startsWith(Object left, Object prefix) {
    return left instanceof String value && prefix instanceof String text && value.startsWith(text);
  }

  private static BigDecimal decimal(Object value) {
    return new BigDecimal(value.toString());
  }
}

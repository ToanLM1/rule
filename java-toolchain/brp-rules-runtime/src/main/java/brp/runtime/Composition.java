package brp.runtime;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;

/** Restricted site-facade aggregators from ADR-7. */
public final class Composition {
  private Composition() {}

  public static BigDecimal sum(List<? extends Number> values) {
    return values.stream()
        .map(value -> new BigDecimal(value.toString()))
        .reduce(BigDecimal.ZERO, BigDecimal::add);
  }

  public static <T> List<T> distinct(List<T> values) {
    return new ArrayList<>(new LinkedHashSet<>(values));
  }

  @SafeVarargs
  public static <T> T firstNonNull(T... values) {
    for (T value : values) if (value != null) return value;
    return null;
  }
}

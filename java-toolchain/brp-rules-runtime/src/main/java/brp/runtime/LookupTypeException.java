package brp.runtime;

/** Lookup result cannot be assigned to the declared IR type. */
public final class LookupTypeException extends RuntimeException {
  public LookupTypeException(String name, String field, Class<?> expected, Class<?> actual) {
    super(
        "Lookup "
            + name
            + "."
            + field
            + " expected "
            + expected.getName()
            + " but got "
            + actual.getName());
  }
}

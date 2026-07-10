package brp.runtime;

import java.util.Map;

/** Missing row or output field in a production lookup. */
public final class MissingLookupException extends RuntimeException {
  public MissingLookupException(String name, Map<String, Object> keys, String field) {
    super("Missing lookup value " + name + "." + field + " for keys " + keys);
  }
}

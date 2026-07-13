package brp.runtime;

import java.util.Map;

/** Site-provided, read-only lookup binding used by generated rules. */
public interface LookupProvider {
  Map<String, Object> lookup(String name, Map<String, Object> keys);

  default <T> T require(String name, Map<String, Object> keys, String field, Class<T> type) {
    Object value = lookup(name, keys).get(field);
    if (value == null) {
      throw new MissingLookupException(name, keys, field);
    }
    if (!type.isInstance(value)) {
      throw new LookupTypeException(name, field, type, value.getClass());
    }
    return type.cast(value);
  }
}

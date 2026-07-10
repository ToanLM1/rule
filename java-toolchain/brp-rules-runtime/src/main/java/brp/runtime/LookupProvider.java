package brp.runtime;

import java.util.Map;

/** Site-provided, read-only lookup binding used by generated rules. */
public interface LookupProvider {
  Map<String, Object> lookup(String name, Map<String, Object> keys);
}

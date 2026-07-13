package brp.seam;

/** Marker until the fixture-specific OpenRewrite recipe is implemented. */
public final class SeamRecipeMarker {
  private SeamRecipeMarker() {}

  public static String name() {
    return "brp-seam-recipes";
  }
}

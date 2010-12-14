package nl.jteam.search.solrext.spatial.lucene.geometry;

import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;

/**
 * Implementation of {@link GeoDistanceCalculator} that assumes that the 2 points are
 * on a flat plane.
 * <p/>
 * Obviously since the world is curved, this calculation with have some error.  However in many cases, the bigger the
 * distance, the less important the error.  The impact of doing such a simple calculation is that the performance of
 * calculating the distance of millions of points is considerably reduced.
 */
public class PlaneGeoDistanceCalculator implements GeoDistanceCalculator {

  private final static double EARTH_CIRCUMFERENCE_MILES = 24901;
  private final static double DISTANCE_PER_DEGREE = EARTH_CIRCUMFERENCE_MILES / 360;

  /**
   * {@inheritDoc}
   */
  public double calculate(
          double sourceLatitude,
          double sourceLongitude,
          double targetLatitude,
          double targetLongitude,
          DistanceUnit unit) {

    double px = targetLongitude - sourceLongitude;
    double py = targetLatitude - sourceLatitude;
    double distanceMiles = Math.sqrt(px * px + py * py) * DISTANCE_PER_DEGREE;
    return DistanceUnit.convert(distanceMiles, DistanceUnit.MILES, unit);
  }
}

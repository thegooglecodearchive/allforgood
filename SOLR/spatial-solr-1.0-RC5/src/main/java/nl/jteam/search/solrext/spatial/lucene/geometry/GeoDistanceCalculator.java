package nl.jteam.search.solrext.spatial.lucene.geometry;

import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;

/**
 * Abstraction of the idea of a calculator of distance between 2 points.  This is useful since while the world is curved,
 * its not always necessary to calcuate the distance between 2 points as if they are on a curve.
 */
public interface GeoDistanceCalculator {

    /**
     * Calculates the distance between the point defined by the source latitude/longitude and the point defined by the
     * target latitude/longitude
     *
     * @param sourceLongitude Longitude of the point the distance is being calculated from
     * @param sourceLatitude Latitude of the point the distance is being calculated from
     * @param targetLongitude Longitude of the point the distance is being calculated to
     * @param targetLatitude Latitude of the point the distance is being calculated to
     * @param unit Unit of distance the result should be returned in
     * @return Distance between the 2 points in the unit of distance requested
     */
    double calculate(double sourceLatitude, double sourceLongitude, double targetLatitude, double targetLongitude, DistanceUnit unit);
}

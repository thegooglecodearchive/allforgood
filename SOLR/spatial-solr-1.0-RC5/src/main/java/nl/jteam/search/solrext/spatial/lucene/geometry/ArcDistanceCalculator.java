package nl.jteam.search.solrext.spatial.lucene.geometry;

import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;

/**
 * Implementation of {@link GeoDistanceCalculator} that calculates distances as though
 * the points are on a globe.
 */
public class ArcDistanceCalculator implements GeoDistanceCalculator {

    /**
     * {@inheritDoc}
     */
    public double calculate(
            double sourceLatitude,
            double sourceLongitude,
            double targetLatitude,
            double targetLongitude,
            DistanceUnit unit) {
        LatLng sourcePoint = new LatLng(sourceLatitude, sourceLongitude);
        LatLng targetPoint = new LatLng(targetLatitude, targetLongitude);
        return DistanceUnit.convert(sourcePoint.arcDistance(targetPoint, DistanceUnit.MILES), DistanceUnit.MILES, unit);
    }
}

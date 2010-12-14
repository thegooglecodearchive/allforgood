package nl.jteam.search.solrext.spatial.lucene.tier.projection;

/**
 * Based on Sinusoidal Projections
 * Project a latitude / longitude on a 2D cartisian map
 */
public class SinusoidalProjector implements Projector {

    /**
     * {@inheritDoc}
     */
    public double[] coords(double latitude, double longitude) {
        double rlat = Math.toRadians(latitude);
        double rlong = Math.toRadians(longitude);
        double nlat = rlong * Math.cos(rlat);
        return new double[]{nlat, rlong};
    }
}

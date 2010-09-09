package nl.jteam.search.solrext.spatial.lucene.tier.projection;

/**
 * Projectors project a longitude/latitude pair to an x/y coordinate pair using standard projection algorithms such as
 * sinusoidal projection.
 */
public interface Projector {

    /**
     * Projects the given latitude and longitude to an x/y coordinate pair
     *
     * @param latitude Latitude to project
     * @param longitude Longitude to project
     * @return x/y coordinate pair created by projecting the latitude and longitude
     */
    public double[] coords(double latitude, double longitude);
}

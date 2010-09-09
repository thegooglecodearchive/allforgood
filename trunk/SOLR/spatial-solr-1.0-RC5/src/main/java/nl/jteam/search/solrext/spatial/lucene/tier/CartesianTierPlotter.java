package nl.jteam.search.solrext.spatial.lucene.tier;

import nl.jteam.search.solrext.spatial.lucene.tier.projection.Projector;

/**
 * CartesianTierPlotter provides functionality for plotting a point defined by a longitude and latitude, in a box thats
 * part of a cartesian tier.
 */
public class CartesianTierPlotter {
    public static final String DEFALT_FIELD_PREFIX = "_tier_";
    
    private static final double IDD = 180;
    private static final double LOG_2 = Math.log(2);

    private final int tierLevel;
    private final int tierLength;
    private final int tierVerticalPosDivider;
    private final Projector projector;

    public CartesianTierPlotter(int tierLevel, Projector projector) {
        this.tierLevel = tierLevel;
        this.projector = projector;

        this.tierLength = (int) Math.pow(2, this.tierLevel);
        this.tierVerticalPosDivider = calculateTierVerticalPosDivider();
    }

    /**
     * Find the tier with the best fit for a bounding box. Best fit is defined as the ceiling of log2 (circumference of
     * earth / distance) distance is defined as the smallest box fitting the corner between a radius and a bounding box.
     * <p/>
     * Distances less than a mile return 15, finer granularity is in accurate
     *
     * @param miles Distance in miles of the bounding box that the tier should be a best fit for
     * @return Tier level with the best fit for the bounding box
     */
    public static int bestFit(double miles) {
        //28,892 a rough circumference of the earth
        int circ = 28892;

        double r = miles / 2.0;

        double corner = r - Math.sqrt(Math.pow(r, 2) / 2.0d);
        double times = circ / corner;
        int bestFit = (int) Math.ceil(log2(times)) + 1;

        if (bestFit > 15) {
            // 15 is the granularity of about 1 mile
            // finer granularity isn't accurate with standard java math
            return 15;
        }
        return bestFit;
    }

    /**
     * TierBoxId is latitude box id + longitude box id where latitude box id, and longitude box id are transposded in to
     * position coordinates.
     *
     * @param latitude Latitude of the point whose box id is to be returned
     * @param longitude Longitude of the point whose box id is to be returned
     * @return Id of the box where the point with the latitude and longitude, is located
     */
    public double getTierBoxId(double latitude, double longitude) {
        double[] coords = projector.coords(latitude, longitude);
        return getBoxId(coords[0]) + (getBoxId(coords[1]) / tierVerticalPosDivider);
    }

    // =============================================== Getters / Setters ===============================================

    /**
     * Calculates the nearest max power of 10 greater than the tierlen
     * <p/>
     * e.g tierId of 13 has tierLen 8192 nearest max power of 10 greater than tierLen would be 10,000
     *
     * @return Nearest max power of 10 greater than the tier len
     */
    private int calculateTierVerticalPosDivider() {
        return (int) Math.pow(10, (int) Math.ceil(Math.log10(this.tierLength)));
    }

    /**
     * Returns the nearest max power of 10 greater than the tier len
     *
     * @return Nearest max power of 10 greater than the tier len
     */
    public double getTierVerticalPosDivider() {
        return tierVerticalPosDivider;
    }

    /**
     * Returns the ID of the tier level plotting is occuring at
     *
     * @return ID of the tier level plotting is occuring at
     */
    public int getTierLevelId() {
        return this.tierLevel;
    }

    // ================================================ Helper Methods =================================================

    /**
     * Returns the box id of the given coordinate
     *
     * @param coord Coordinate whose box id is to be computed
     * @return Box id of the coordinate
     */
    private double getBoxId(double coord) {
        return Math.floor(coord / (IDD / this.tierLength));
    }

    /**
     * Computes log to base 2 of the given value
     *
     * @param value Value to compute the log of
     * @return Log_2 of the value
     */
    public static double log2(double value) {
        return Math.log(value) / LOG_2;
    }
}

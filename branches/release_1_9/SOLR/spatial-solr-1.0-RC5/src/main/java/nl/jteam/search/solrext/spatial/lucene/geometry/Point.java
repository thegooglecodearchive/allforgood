package nl.jteam.search.solrext.spatial.lucene.geometry;

/**
 * Class representing a point consisting simply of an x and y coordinate
 */
public class Point {
    
    private double x;
    private double y;

    /**
     * Constructs a new point consisting of the given x and y coordinates
     *
     * @param x x coordinate of point
     * @param y y coordinate of point
     */
    public Point(double x, double y) {
        this.x = x;
        this.y = y;
    }

    // =============================================== Getters / Setters ===============================================

    /**
     * Returns the x coordinate
     *
     * @return x coordinate
     */
    public double getX() {
        return x;
    }

    /**
     * Returns the y coordinate
     *
     * @return y coordinate
     */
    public double getY() {
        return y;
    }
}

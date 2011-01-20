package nl.jteam.search.solrext.spatial.lucene.geometry;

/**
 * Rectangle shape.
 *
 * @author Chris Male
 */
public class Rectangle {
    
    private Point ptMin;
    private Point ptMax;

    public Rectangle(double x1, double y1, double x2, double y2) {
        this.ptMin = new Point(Math.min(x1, x2), Math.min(y1, y2));
        this.ptMax = new Point(Math.max(x1, x2), Math.max(y1, y2));
    }

    /**
     * Determines whether the Rectangle contains the given point
     * 
     * @param point Point to check if the rectangle contains it
     * @return {@code true} if the Rectangle contains the point, {@code false} otherwise
     */
    public boolean contains(Point point) {
        return point.getX() >= ptMin.getX() &&
               point.getX() <= ptMax.getX() &&
               point.getY() >= ptMin.getY() &&
               point.getY() <= ptMax.getY();
    }

    // =============================================== Getters / Setters ===============================================

    public Point getMaxPoint() {
        return ptMax;
    }

    public Point getMinPoint() {
        return ptMin;
    }
}

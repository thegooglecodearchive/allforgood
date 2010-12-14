package nl.jteam.search.solrext.spatial.lucene.tier;

import java.util.ArrayList;
import java.util.List;

/**
 * CartesianShape contains information related to a shape created on a specific cartesian tier.  Because the tiers consist
 * of a set of boxes, shapes are defined simply by what boxes the shape overlaps, and what tier level the boxes are at.
 * Such a simply approximation will result in points being included that are not in the actual shape, but this fine grained
 * filtering is left out of the cartesian shape filtering process.
 */
public class CartesianShape {

    private List<Double> boxIds = new ArrayList<Double>();
    private int tierId;

    /**
     * Creates a new CartesianShape that represents a shape at the given tier level
     *
     * @param tierId ID of the tier level that the shape is in
     */
    public CartesianShape(int tierId) {
        this.tierId = tierId;
    }

    /**
     * Adds the given box id to the list of boxes this shape overlaps
     *
     * @param boxId ID of a box that this shape overlaps
     */
    public void addBoxId(double boxId) {
        boxIds.add(boxId);
    }

    // =============================================== Getters / Setters ===============================================
    
    /**
     * Returns the list of ids of the boxes that this shape overlaps
     *
     * @return List of ids of the boxes the shape overlaps.  Always non-null.
     */
    public List<Double> getBoxIds() {
        return boxIds;
    }

    /**
     * Returns the tier level ID that this shape is in
     *
     * @return Tier level id that this shape is in
     */
    public int getTierId() {
        return tierId;
    }
}

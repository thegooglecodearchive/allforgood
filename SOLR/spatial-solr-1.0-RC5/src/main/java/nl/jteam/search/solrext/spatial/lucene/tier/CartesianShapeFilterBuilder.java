package nl.jteam.search.solrext.spatial.lucene.tier;

import nl.jteam.search.solrext.spatial.lucene.geometry.Rectangle;
import nl.jteam.search.solrext.spatial.lucene.tier.projection.Projector;
import nl.jteam.search.solrext.spatial.lucene.tier.projection.SinusoidalProjector;
import nl.jteam.search.solrext.spatial.lucene.util.DistanceApproximation;
import org.apache.lucene.search.Filter;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.logging.Logger;
import java.util.logging.Level;

/**
 *
 */
public class CartesianShapeFilterBuilder {

    private static final Projector PROJECTOR = new SinusoidalProjector();
    private static final Logger log = Logger.getLogger(CartesianShapeFilterBuilder.class.getName());

    private final String tierPrefix;

    public CartesianShapeFilterBuilder(String tierPrefix) {
        this.tierPrefix = tierPrefix;
    }

    public Filter buildFilter(double latitude, double longitude, double miles) {
        CartesianShape cartesianShape = getBoxShape(latitude, longitude, miles);
        return new CartesianShapeFilter(cartesianShape, tierPrefix + cartesianShape.getTierId());
    }

    // ================================================ Helper Methods =================================================
    
    private CartesianShape getBoxShape(double latitude, double longitude, double miles) {
        Rectangle box = getBoundary(latitude, longitude, miles);

        double latY = box.getMaxPoint().getY();
        double latX = box.getMinPoint().getY();

        double longY = box.getMaxPoint().getX();
        double longX = box.getMinPoint().getX();

        int bestFit = CartesianTierPlotter.bestFit(miles);

        if (log.isLoggable(Level.FINE)) {
            log.info("Best Fit is : " + bestFit);
        }
        CartesianTierPlotter ctp = new CartesianTierPlotter(bestFit, PROJECTOR);
        CartesianShape cartesianShape = new CartesianShape(bestFit);

        // generate shape
        // iterate from startX->endX
        //     iterate from startY -> endY
        //      shape.add(currentLat.currentLong);


        double beginAt = ctp.getTierBoxId(latX, longX);
        double endAt = ctp.getTierBoxId(latY, longY);

        double tierVert = ctp.getTierVerticalPosDivider();
        if (log.isLoggable(Level.FINE)) {
            log.fine(" | " + beginAt + " | " + endAt);
        }

        double startX = beginAt - (beginAt % 1);
        double startY = beginAt - startX; //should give a whole number

        double endX = endAt - (endAt % 1);
        double endY = endAt - endX; //should give a whole number

        int scale = (int) Math.log10(tierVert);
        endY = new BigDecimal(endY).setScale(scale, RoundingMode.HALF_EVEN).doubleValue();
        startY = new BigDecimal(startY).setScale(scale, RoundingMode.HALF_EVEN).doubleValue();
        if (log.isLoggable(Level.FINE)) {
            log.fine("scale " + scale + " startX " + startX + " endX " + endX + " startY " + startY + " endY " + endY + " tierVert " + tierVert);
        }

        double xInc = 1.0d / tierVert;
        xInc = new BigDecimal(xInc).setScale(scale, RoundingMode.HALF_EVEN).doubleValue();

        for (; startX <= endX; startX++) {
            double itY = startY;
            while (itY <= endY) {
                double boxId = startX + itY;
                cartesianShape.addBoxId(boxId);
                // java keeps 0.0001 as 1.0E-1 which ends up as 0.00011111
                itY = new BigDecimal(itY + xInc).setScale(scale, RoundingMode.HALF_EVEN).doubleValue();
            }
        }
        return cartesianShape;
    }

    private Rectangle getBoundary(double x1, double y1, double miles) {
        double miplatdeg = DistanceApproximation.getMilesPerLngDeg(x1);
        double miplngdeg = DistanceApproximation.getMilesPerLatDeg();

        double lngDelta = (miles / 2) / miplngdeg;
        double latDelta = (miles / 2) / miplatdeg;

        return new Rectangle(y1 - lngDelta, x1 - latDelta, y1 + lngDelta, x1 + latDelta);
    }
}

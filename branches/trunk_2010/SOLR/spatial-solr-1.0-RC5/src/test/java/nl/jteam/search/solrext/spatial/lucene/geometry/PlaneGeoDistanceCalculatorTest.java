package nl.jteam.search.solrext.spatial.lucene.geometry;

import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;
import nl.jteam.search.solrext.spatial.lucene.geometry.PlaneGeoDistanceCalculator;
import org.junit.Test;
import static org.junit.Assert.assertEquals;

/**
 * Tests for {@link nl.jteam.search.solrext.spatial.lucene.geometry.PlaneGeoDistanceCalculator}
 */
public class PlaneGeoDistanceCalculatorTest {

    /**
     * Pass condition: The distance calculated in miles matches the expected distance
     */
    @Test
    public void testCalculate_miles() {
        double distance = new PlaneGeoDistanceCalculator().calculate(53.85, 4.51, 43.22, 9.68, DistanceUnit.MILES);
        assertEquals(817.6220401155788, distance, 0D);
    }

    /**
     * Pass condition: The distance calculated in kilometers matches the expected distance
     */
    @Test
    public void testCalculate_kilometers() {
        double distance = new PlaneGeoDistanceCalculator().calculate(53.85, 4.51, 43.22, 9.68, DistanceUnit.KILOMETERS);
        assertEquals(1315.835124527766, distance, 0D);
    }
}

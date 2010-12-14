package nl.jteam.search.solrext.spatial.lucene.geometry;

import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;
import nl.jteam.search.solrext.spatial.lucene.geometry.ArcDistanceCalculator;
import org.junit.Test;
import static org.junit.Assert.assertEquals;

/**
 * Tests for {@link nl.jteam.search.solrext.spatial.lucene.geometry.ArcDistanceCalculator}
 */
public class ArcDistanceCalculatorTest {

    /**
     * Pass condition: The distance calculated in miles matches the expected distance
     */
    @Test
    public void testCalculate_miles() {
        double distance = new ArcDistanceCalculator().calculate(53.85, 4.51, 43.22, 9.68, DistanceUnit.MILES);
        assertEquals(771.9580677520433, distance, 0D);
    }

    /**
     * Pass condition: The distance calculated in kilometers matches the expected distance
     */
    @Test
    public void testCalculate_kilometers() {
        double distance = new ArcDistanceCalculator().calculate(53.85, 4.51, 43.22, 9.68, DistanceUnit.KILOMETERS);
        assertEquals(1242.3460845883446, distance, 0D);
    }
}

package nl.jteam.search.solrext.spatial.lucene.util;

import static org.junit.Assert.assertEquals;
import org.junit.Test;
import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;

/**
 * Tests for {@link nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit}
 *
 * @author Chris Male
 */
public class DistanceUnitTest {

    /**
     * Pass condition: When finding the DistanceUnit for "km", KILOMETRES is found.  When finding the DistanceUnit for
     *                 "miles", MILES is found.
     */
    @Test
    public void testFindDistanceUnit() {
        assertEquals(DistanceUnit.KILOMETERS, DistanceUnit.findDistanceUnit("km"));
        assertEquals(DistanceUnit.MILES, DistanceUnit.findDistanceUnit("miles"));
    }

    /**
     * Pass condition: Searching for the DistanceUnit of an unknown unit "mls" should throw an IllegalArgumentException.
     */
    @Test(expected = IllegalArgumentException.class)
    public void testFindDistanceUnit_unknownUnit() {
        DistanceUnit.findDistanceUnit("mls");
    }

    /**
     * Pass condition: Converting between the same units should not change the value.  Converting from MILES to KILOMETRES
     *                 involves multiplying the distance by the ratio, and converting from KILOMETRES to MILES involves
     *                 dividing by the ratio
     */
    @Test
    public void testConvert() {
        assertEquals(10.5, DistanceUnit.convert(10.5, DistanceUnit.MILES, DistanceUnit.MILES), 0D);
        assertEquals(10.5, DistanceUnit.convert(10.5, DistanceUnit.KILOMETERS, DistanceUnit.KILOMETERS), 0D);
        assertEquals(10.5 * 1.609344, DistanceUnit.convert(10.5, DistanceUnit.MILES, DistanceUnit.KILOMETERS), 0D);
        assertEquals(10.5 / 1.609344, DistanceUnit.convert(10.5, DistanceUnit.KILOMETERS, DistanceUnit.MILES), 0D);
    }
}

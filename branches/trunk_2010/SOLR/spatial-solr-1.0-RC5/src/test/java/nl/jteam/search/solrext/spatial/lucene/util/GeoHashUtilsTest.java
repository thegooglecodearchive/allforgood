package nl.jteam.search.solrext.spatial.lucene.util;

import org.junit.Test;
import static org.junit.Assert.assertEquals;
import nl.jteam.search.solrext.spatial.lucene.util.GeoHashUtils;

/**
 * Tests for {@link nl.jteam.search.solrext.spatial.lucene.util.GeoHashUtils}
 * 
 * @author Chris Male
 */
public class GeoHashUtilsTest {

    /**
     * Pass condition: lat=42.6, lng=-5.6 should be encoded as "ezs42e44yx96", lat=57.64911 lng=10.40744 should be encoded
     *                 as "u4pruydqqvj8"
     */
    @Test
    public void testEncode() {
        String hash = GeoHashUtils.encode(42.6, -5.6);
        assertEquals("ezs42e44yx96", hash);

        hash = GeoHashUtils.encode(57.64911, 10.40744);
        assertEquals("u4pruydqqvj8", hash);
    }

    /**
     * Pass condition: lat=52.3738007, lng=4.8909347 should be encoded and then decoded within 0.00001 of the original value
     */
    @Test
    public void testDecode_preciseLongitudeLatitude() {
        String hash = GeoHashUtils.encode(52.3738007, 4.8909347);

        double[] latitudeLongitude = GeoHashUtils.decode(hash);

        assertEquals(52.3738007, latitudeLongitude[0], 0.00001D);
        assertEquals(4.8909347, latitudeLongitude[1], 0.00001D);
    }

    /**
     * Pass condition: lat=84.6, lng=10.5 should be encoded and then decoded within 0.00001 of the original value
     */
    @Test
    public void testDecode_impreciseLongitudeLatitude() {
        String hash = GeoHashUtils.encode(84.6, 10.5);

        double[] latitudeLongitude = GeoHashUtils.decode(hash);

        assertEquals(84.6, latitudeLongitude[0], 0.00001D);
        assertEquals(10.5, latitudeLongitude[1], 0.00001D);
    }
}

package nl.jteam.search.solrext.spatial.lucene.util;

import org.apache.lucene.util.OpenBitSet;
import org.junit.Test;
import static org.junit.Assert.assertEquals;
import nl.jteam.search.solrext.spatial.lucene.util.OpenBitSetUtils;

/**
 * Tests for {@link nl.jteam.search.solrext.spatial.lucene.util.OpenBitSetUtils}
 * 
 * @author Chris Male
 */
public class OpenBitSetUtilsTest {

    /**
     * Pass condition: For a bit set at index 10, the length result is 10 + 1 = 11
     */
    @Test
    public void testLength_oneBitSet() {
        OpenBitSet openBitSet = new OpenBitSet();
        openBitSet.set(10);
        assertEquals(11, OpenBitSetUtils.length(openBitSet));
    }

    /**
     * Pass condition: Checks that setting the maximum long length is handled correctly. length result 64 + 1 = 65
     */
    public void testLength_64Index() {
        OpenBitSet openBitSet = new OpenBitSet();
        openBitSet.set(64);
        assertEquals(65, OpenBitSetUtils.length(openBitSet));
    }

    /**
     * Pass condition: 2 set bits, highest with index 36, length result 36 + 1 = 37
     */
    public void testLength_twoBitsSetSameWord() {
        OpenBitSet openBitSet = new OpenBitSet();
        openBitSet.set(10);
        openBitSet.set(36);
        assertEquals(37, OpenBitSetUtils.length(openBitSet));
    }

    /**
     * Pass condition: 2 set bits in different words, highest with ineex 9854, length result 9854 + 1 = 9855
     */
    public void testLength_twoBitsDifferentWordsNotFirst() {
        OpenBitSet openBitSet = new OpenBitSet();
        openBitSet.set(654);
        openBitSet.set(9854);
        assertEquals(9855, OpenBitSetUtils.length(openBitSet));
    }
}

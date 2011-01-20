package nl.jteam.search.solrext.spatial.lucene.util;

import org.apache.lucene.util.OpenBitSet;

/**
 * Utilities that extend the functionality of OpenBitSet
 * 
 * @author Chris Male
 */
public class OpenBitSetUtils {

    private OpenBitSetUtils() {
    }

    /**
     * Returns the index of the highest set bit in the given OpenBitSet plus one.  This replicates the functionality of
     * {@link java.util.BitSet#length()}
     *
     * @param openBitSet OpenBitSet to compute the highest set bit in
     * @return Index of the highest set bit plus one, or {@code 0} if no bit is set
     */
    public static int length(OpenBitSet openBitSet) {
        int numWords = openBitSet.getNumWords();
        if (numWords == 0) {
            return 0;
        }
        long lastUsedWord = openBitSet.getBits()[numWords - 1];
        for (int i = 0; i < 63; i++) {
            long mask = 1L << (62 - i);
            if ((mask & lastUsedWord) == mask) {
                return ((numWords - 1) * 64) + (62 - i) + 1; 
            }
        }
        return 0;
    }
}

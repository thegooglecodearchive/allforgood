package nl.jteam.search.solrext.spatial.lucene.distance;

import org.apache.lucene.index.IndexReader;

import java.util.Map;
import java.util.BitSet;
import java.io.IOException;

/**
 * DistanceFilter is responsible for filtering out documents from an existing BitSet, based on their calculated distance
 * from the central point.  Because the costing of calculating distances for documents is relatively high, this filter
 * uses an existing BitSet, which will have been created another filter previously.  As such, this is technicall not
 * a Lucene Filter.
 * <p/>
 * In addition to filtering out documents, the filter also holds onto the calculated distances so they can be used after
 * the filtering process.
 */
public interface DistanceFilter {

    /**
     * Returns a map of calculated distances by document ids
     *
     * @return Map of calculated distances by document ids
     */
    Map<Integer, Double> getDistances();

    /**
     * Returns the calculated distance for a document with the given id
     *
     * @param docId ID of the document whose distance is to be returned
     * @return Calculated distance of the document with the id
     */
    Double getDistance(int docId);

    /**
     * Filters the documents from the given IndexReader who have bits set in the given BitSet.
     *
     * @param reader IndexReader from where the documents will be read from
     * @param bits BitSet containing bits indicating which documents should be considered to be filtered out
     * @return BitSet with bits set representing those documents that passed the filter
     * @throws java.io.IOException Can be thrown while reading from the IndexReader
     */
    BitSet bits(IndexReader reader, BitSet bits) throws IOException;
}

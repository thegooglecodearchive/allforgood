package nl.jteam.search.solrext.spatial.lucene.distance;

import org.apache.lucene.index.IndexReader;

import java.util.Map;
import java.util.Collections;
import java.util.BitSet;
import java.io.IOException;

/**
 * Implementation of {@link DistanceFilter} that does no actual filtering.  This means
 * that there can always be a DistanceFilter instantiated in {@link nl.jteam.search.solrext.spatial.lucene.SpatialFilter}, but that
 * the actual process of filtering documents by their distance, which is a computationally expensive process, doesn't
 * always have to occur.
 */
public class NoOpDistanceFilter implements DistanceFilter {

    private Map<Integer, Double> distancesById = Collections.EMPTY_MAP;

    /**
     * {@inheritDoc}
     */
    public Map<Integer, Double> getDistances() {
        return distancesById;
    }

    /**
     * {@inheritDoc}
     */
    public Double getDistance(int docId) {
        return distancesById.get(docId);
    }

    /**
     * Executes no filtering.  Simply returns the given BitSet
     * <p/>
     * {@inheritDoc}
     */
    public BitSet bits(IndexReader reader, BitSet bits) throws IOException {
        return bits;
    }
}

package nl.jteam.search.solrext.spatial;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.apache.lucene.document.Fieldable;
import org.apache.lucene.document.Field;
import nl.jteam.search.solrext.spatial.lucene.SpatialFilter;

/**
 * Implementation of {@link FieldValueSource} that uses the values calculated by
 * {@link nl.jteam.search.solrext.spatial.lucene.SpatialFilter} to add in the calculated distances of documents
 *
 * @author Chris Male
 */
public class DistanceFieldValueSource implements FieldValueSource {

    private static final Logger logger = LoggerFactory.getLogger(DistanceFieldValueSource.class);

    private SpatialFilter spatialFilter;
    private String distanceFieldName;

    /**
     * Creates a new DistanceFieldValueSource that uses the values computed by the given SpatialFilter and adds them under
     * the given field name
     *
     * @param spatialFilter SpatialFilter that can be used to access the computed values
     * @param distanceFieldName Name of the field that the distance values should be added under
     */
    public DistanceFieldValueSource(SpatialFilter spatialFilter, String distanceFieldName) {
        this.spatialFilter = spatialFilter;
        this.distanceFieldName = distanceFieldName;
    }

    /**
     * {@inheritDoc}
     */
    public String getFieldName() {
        return distanceFieldName;
    }

    /**
     * {@inheritDoc}
     */
    public boolean shouldOverride() {
        return true;
    }

    /**
     * {@inheritDoc}
     */
    public Fieldable[] getValues(int docId) {
        Double docDistance = spatialFilter.getDistanceFilter().getDistance(docId);
        if (logger.isDebugEnabled()) {
            logger.debug("Retrieved distance {} for doc {}", docDistance, docId);
        }
      if(docDistance == null) return null;
        Fieldable fieldable = new Field(distanceFieldName, docDistance.toString(), Field.Store.YES, Field.Index.NO);
        return new Fieldable[]{fieldable};
    }
}


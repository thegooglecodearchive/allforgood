package nl.jteam.search.solrext.spatial.lucene.distance;

import org.apache.lucene.index.IndexReader;

import java.io.IOException;

/**
 * Factory for instances of {@link LocationDataSet}
 */
public interface LocationDataSetFactory {

    /**
     * Builds a LocationDataSet based on the data read from the given IndexReader
     *
     * @param indexReader IndexReader from where the location data will be read
     * @return LocationDataSet representing the location data of the documents in the index
     * @throws java.io.IOException Can be thrown while reading from the IndexReader
     */
    LocationDataSet buildLocationDataSet(IndexReader indexReader) throws IOException;
}

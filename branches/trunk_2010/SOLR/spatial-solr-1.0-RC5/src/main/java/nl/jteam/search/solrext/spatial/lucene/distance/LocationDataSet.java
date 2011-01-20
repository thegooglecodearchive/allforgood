package nl.jteam.search.solrext.spatial.lucene.distance;

import nl.jteam.search.solrext.spatial.lucene.geometry.Point;

/**
 * LocationDataSet is an abstracts away the format of the data that defines the location of a document.  It means that
 * different formats can be used, whether they be 2 fields for latitude and longitude, or 1 field with a geohash, without
 * having to change the code that uses the data.
 */
public interface LocationDataSet {

    /**
     * Returns the point (defined by an x/y coordinate) of the document with the given id
     *
     * @param docId ID of the document whose point is to be returned
     * @return Point (defined by an x/y coordinate) of the document with the given id
     */
    Point getPoint(int docId);
}

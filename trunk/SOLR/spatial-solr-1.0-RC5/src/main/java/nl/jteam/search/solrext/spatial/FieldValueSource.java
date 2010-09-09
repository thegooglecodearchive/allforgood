package nl.jteam.search.solrext.spatial;

import org.apache.lucene.document.Fieldable;

/**
 * FieldValueSource provides a generic way to add arbitrary data to the documents returned by Solr.  By creating and
 * registering instances of FieldValueSource with {@link FieldValueSourceRegistry}, it is possible
 * for information from any source to be added to the documents Solr includes in its search results.
 *
 * @author Chris Male
 * @see FieldValueSourceRegistry
 */
public interface FieldValueSource {

    /**
     * Returns the name of the field that the source applies to.  The name does not necessarily have to have been declared
     * in the schema.xml.
     *
     * @return Name of the field the source applies to
     */
    String getFieldName();

    /**
     * Returns whether the values returned by this source should override values belonging to the same field.
     *
     * @return {@code true} if the values should override any existing ones, {@code false} if they should only be added
     */
    boolean shouldOverride();

    /**
     * Returns the values calculated by the source for the document with the given id
     *
     * @param docId ID of the document whose values should be returned from the source
     * @return Values calculated by the source for the document with the ID
     */
    Fieldable[] getValues(int docId);
}
